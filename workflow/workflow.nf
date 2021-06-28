#!/usr/bin/env nextflow

params.input_spectra = 'test/GNPS00002_A3_p.mzML'
params.query = "QUERY scaninfo(MS2DATA)"

_spectra_ch = Channel.fromPath( params.input_spectra )

TOOL_FOLDER = "$baseDir/bin"
params.publishdir = "nf_output"

process queryData {
    publishDir "$params.publishdir/msql", mode: 'copy'
    
    input:
    file input_spectrum from _spectra_ch

    output:
    file "*_output.tsv" into _query_results_ch

    """
    python $TOOL_FOLDER/msql_cmd.py \
        --output_file ${input_spectrum}_output.tsv \
        $input_spectrum \
        "${params.query}"
    """
}
