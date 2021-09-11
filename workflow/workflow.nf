#!/usr/bin/env nextflow

params.input_spectra = 'data/GNPS00002_A3_p.mzML'
params.query = "QUERY scaninfo(MS2DATA)"
params.parallel_files = 'NO'
params.parallel_query = 'NO'
params.extract = 'YES'

_spectra_ch = Channel.fromPath( params.input_spectra )
_spectra_ch.into{_spectra_ch1;_spectra_ch2}

_spectra_ch3 = _spectra_ch1.map { file -> tuple(file, file.toString().replaceAll("/", "_").replaceAll(" ", "_"), file) }

TOOL_FOLDER = "$baseDir/bin"
params.publishdir = "nf_output"
params.PYTHONRUNTIME = "python" // this is a hack because CCMS cluster does not have python installed

if(params.parallel_files == "YES"){
    process queryData {
        errorStrategy 'ignore'
        time '4h'
        //maxRetries 3
        //memory { 6.GB * task.attempt }
        memory { 12.GB }

        //publishDir "$params.publishdir/msql_temp", mode: 'copy'
        
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
            --query "${params.query}" \
            --output_file "${mangled_output_filename}_output.tsv" \
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
        time '4h'
        
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
            --query "${params.query}" \
            --output_file "${mangled_output_filename}_output.tsv" \
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
        errorStrategy 'ignore'
        
        input:
        file "json/*" from _query_extract_results_ch.collect()

        output:
        file "extracted_mzML" optional true
        file "extracted_mgf" optional true
        file "extracted.tsv" optional true
        file "extracted_json" optional true into _extracted_json_ch

        """
        mkdir extracted_mzML
        mkdir extracted_mgf
        mkdir extracted_json
        $params.PYTHONRUNTIME $TOOL_FOLDER/merged_extracted.py \
        json \
        extracted_mzML \
        extracted_mgf \
        extracted_json \
        extracted.tsv 
        """
    }

    // process summarizeExtracted {
    //     publishDir "$params.publishdir/summary", mode: 'copy'
    //     cache false
    //     echo true
    //     errorStrategy 'ignore'
        
    //     input:
    //     file(extracted_json) from _extracted_json_ch

    //     output:
    //     file "summary_extracted.html" optional true

    //     """
    //     $params.PYTHONRUNTIME $TOOL_FOLDER/summarize_extracted.py \
    //     $extracted_json \
    //     summary_extracted.html
    //     """
    // }
}


process summarizeResults {
    publishDir "$params.publishdir/summary", mode: 'copy'
    cache false
    echo true
    errorStrategy 'ignore'

    input:
    file(merged_results) from _query_results_merged_ch

    output:
    file "summary.html" optional true

    """
    $params.PYTHONRUNTIME $TOOL_FOLDER/summarize_results.py \
    $merged_results \
    summary.html
    """
}



