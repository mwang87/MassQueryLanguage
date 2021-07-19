#!/usr/bin/env nextflow

params.input_spectra = 'test/GNPS00002_A3_p.mzML'
params.query = "QUERY scaninfo(MS2DATA)"
params.parallel_files = 'NO'
params.parallel_query = 'NO'
params.extract = 'YES'

_spectra_ch = Channel.fromPath( params.input_spectra )
_spectra_ch.into{_spectra_ch1;_spectra_ch2}

_spectra_ch3 = _spectra_ch1.map { file -> tuple(file, file.toString().replaceAll("/", "_"), file) }

TOOL_FOLDER = "$baseDir/bin"
params.publishdir = "nf_output"
params.PYTHONRUNTIME = "python" // this is a hack because CCMS cluster does not have python installed

if(params.parallel_files == "YES"){
    process queryData {
        //errorStrategy 'ignore'
        time '2h'
        
        // This enable multiple retries with increasing ram, and if this all fails, lets retire it
        // https://github.com/nextflow-io/nextflow/issues/563
        maxRetries 3
        errorStrategy { (task.exitStatus in 137..140 && task.attempt <= maxRetries)  ? 'retry' : 'ignore' }
        memory { 8.GB + 12.G * task.attempt }

        publishDir "$params.publishdir/msql", mode: 'copy'
        
        input:
        set val(filepath), val(mangled_output_filename), file(input_spectrum) from _spectra_ch3

        output:
        file "*_output.tsv" optional true into _query_results_ch
        file "*_extract.json" optional true into _query_extract_results_ch

        script:
        def extractflag = params.extract == 'YES' ? "--extract_json ${mangled_output_filename}_extract.json" : ''
        """
        $params.PYTHONRUNTIME $TOOL_FOLDER/msql_cmd.py \
            "$input_spectrum" \
            "${params.query}" \
            --output_file ${mangled_output_filename}_output.tsv \
            --parallel_query $params.parallel_query \
            --cache NO \
            --original_path "$filepath" \
            $extractflag
        """
    }
}
else{
    process queryData2 {
        echo true
        errorStrategy 'ignore'
        maxForks 1
        time '2h'
        
        publishDir "$params.publishdir/msql_temp", mode: 'copy'
        
        input:
        set val(filepath), val(mangled_output_filename), file(input_spectrum) from _spectra_ch3

        output:
        file "*_output.tsv" optional true into _query_results_ch
        file "*_extract.json" optional true into _query_extract_results_ch

        script:
        def extractflag = params.extract == 'YES' ? "--extract_json ${mangled_output_filename}_extract.json" : ''
        """
        $params.PYTHONRUNTIME $TOOL_FOLDER/msql_cmd.py \
            "$input_spectrum" \
            "${params.query}" \
            --output_file ${mangled_output_filename}_output.tsv \
            --parallel_query $params.parallel_query \
            --cache NO \
            --original_path "$filepath" \
            $extractflag
        """
    }
}

// Merging the results
_query_results_merged_ch = Channel.create()
_query_results_ch.collectFile(name: "merged_query_results.tsv", storeDir: "$params.publishdir/msql", keepHeader: true).into(_query_results_merged_ch)

if(params.extract == "YES"){
    // Extracting the spectra
    process formatExtractedSpectra {
        publishDir "$params.publishdir/extracted", mode: 'copy'
        cache false
        
        input:
        file "json/*" from _query_extract_results_ch.collect()

        output:
        file "extracted.*" optional true

        """
        $params.PYTHONRUNTIME $TOOL_FOLDER/merged_extracted.py \
        json \
        extracted.mzML \
        extracted.mgf \
        extracted.tsv
        """
    }
}
