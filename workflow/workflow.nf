#!/usr/bin/env nextflow

params.input_spectra = 'test/GNPS00002_A3_p.mzML'
params.query = "QUERY scaninfo(MS2DATA)"
params.parallel_files = 'NO'
params.parallel_query = 'NO'
params.extract = 'YES'

_spectra_ch = Channel.fromPath( params.input_spectra )
_spectra_ch.into{_spectra_ch1;_spectra_ch2}

_spectra_ch3 = _spectra_ch1.map { file -> tuple(file, file) }

TOOL_FOLDER = "$baseDir/bin"
params.publishdir = "nf_output"

if(params.parallel_query == "YES"){
    process queryData {
        errorStrategy 'ignore'

        publishDir "$params.publishdir/msql", mode: 'copy'
        
        input:
        set val(filepath), file(input_spectrum) from _spectra_ch3

        output:
        file "*_output.tsv" optional true into _query_results_ch

        """
        python $TOOL_FOLDER/msql_cmd.py \
            --output_file ${input_spectrum}_output.tsv \
            $input_spectrum \
            "${params.query}" \
            --parallel_query $params.parallel_query \
            --cache NO \
            --original_path "$filepath"
        """
    }
}
else{
    process queryData2 {
        echo true
        errorStrategy 'ignore'
        maxForks 1
        
        publishDir "$params.publishdir/msql", mode: 'copy'
        
        input:
        set val(filepath), file(input_spectrum) from _spectra_ch3

        output:
        file "*_output.tsv" optional true into _query_results_ch

        """
        python $TOOL_FOLDER/msql_cmd.py \
            --output_file ${input_spectrum}_output.tsv \
            $input_spectrum \
            "${params.query}" \
            --parallel_query $params.parallel_query \
            --cache NO \
            --original_path "$filepath"
        """
    }
}

// Merging the results
_query_results_merged_ch = Channel.create()
_query_results_ch.collectFile(name: "merged_query_results.tsv", storeDir: "$params.publishdir/msql", keepHeader: true).into(_query_results_merged_ch)

if(params.extract == "YES"){
    // Extracting the spectra
    process extractSpectra {
        publishDir "$params.publishdir/extracted", mode: 'copy'
        
        input:
        file query_results from _query_results_merged_ch
        file "files/*" from _spectra_ch2

        output:
        file "extracted.*" optional true

        """
        python $TOOL_FOLDER/msql_extract.py \
        files \
        $query_results \
        extracted.mgf \
        extracted.mzML \
        extracted.tsv
        """
    }
}
