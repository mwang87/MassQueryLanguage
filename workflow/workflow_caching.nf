#!/usr/bin/env nextflow

params.input_spectra = 'data/GNPS00002_A3_p.mzML'

_spectra_ch = Channel.fromPath( params.input_spectra )
_spectra_ch.into{_spectra_ch1;_spectra_ch2}

_spectra_ch3 = _spectra_ch1.map { file -> tuple(file, file.toString().replaceAll("/", "_").replaceAll(" ", "_"), file) }

TOOL_FOLDER = "$baseDir/bin"
params.publishdir = "nf_output"
params.PYTHONRUNTIME = "python" // this is a hack because CCMS cluster does not have python installed

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
    file "*parquet"

    """
    $params.PYTHONRUNTIME $TOOL_FOLDER/msql_cmd.py \
        "$input_spectrum" \
        --original_path "$filepath"
    """
}