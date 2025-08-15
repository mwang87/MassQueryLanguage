#!/usr/bin/env nextflow
nextflow.enable.dsl=2

params.input_spectra = 'data' // We assume we pass it a folder with spectra files
params.query = "QUERY scaninfo(MS2DATA)"
params.parallel_files = 'NO'
params.parallel_query = 'NO' // Likely never to turn this on
params.extract = 'YES'
params.extractnaming = 'condensed' //condensed means it is mangled, original means the original mzML filenames
params.maxfilesize = "3000" // Default 3000 MB

TOOL_FOLDER = "$baseDir/bin"
params.publishdir = "$launchDir"
params.PYTHONRUNTIME = "python" // this is a hack because CCMS cluster does not have python installed


// COMPATIBILITY NOTE: The following might be necessary if this workflow is being deployed in a slightly different environemnt
// checking if outdir is defined,
// if so, then set publishdir to outdir
if (params.outdir) {
    _publishdir = params.outdir
}
else{
    _publishdir = params.publishdir
}

// Augmenting with nf_output
_publishdir = "${_publishdir}/nf_output"

// This is the parallel run that will run on the cluster
process queryData {
    errorStrategy 'ignore'
    time '4h'
    //maxRetries 3

    //memory { 6.GB * task.attempt }
    //memory 12.GB

    conda "$TOOL_FOLDER/conda_env.yml"

    input:
    tuple val(filepath), val(mangled_output_filename), file(input_spectrum)

    output:
    file "*_output.tsv" optional true
    file "*_extract.json" optional true

    script:
    def extractflag = params.extract == 'YES' ? "--extract_json ${mangled_output_filename}_extract.json" : ''
    """
    $params.PYTHONRUNTIME $TOOL_FOLDER/msql_cmd.py \
        "$input_spectrum" \
        "${params.query}" \
        --output_file "${mangled_output_filename}_output.tsv" \
        --parallel_query $params.parallel_query \
        --cache NO \
        --original_path "$filepath" \
        $extractflag \
        --maxfilesize $params.maxfilesize
    """
}
process queryData2 {
    errorStrategy 'ignore'
    maxForks 1
    time '4h'
    
    //publishDir "$params.publishdir/msql_temp", mode: 'copy'
    conda "$TOOL_FOLDER/conda_env.yml"
    
    input:
    tuple val(filepath), val(mangled_output_filename), file(input_spectrum)

    output:
    file "*_output.tsv" optional true
    file "*_extract.json" optional true

    script:
    def extractflag = params.extract == 'YES' ? "--extract_json ${mangled_output_filename}_extract.json" : ''
    """
    $params.PYTHONRUNTIME $TOOL_FOLDER/msql_cmd.py \
        "$input_spectrum" \
        "${params.query}" \
        --output_file "${mangled_output_filename}_output.tsv" \
        --parallel_query $params.parallel_query \
        --cache NO \
        --original_path "$filepath" \
        $extractflag \
        --maxfilesize $params.maxfilesize
    """
}

// Merging the results, 100 results at a time, and then doing a full merge
process formatResultsMergeRounds {
    publishDir "$_publishdir/msql", mode: 'copy'
    cache false

    //errorStrategy 'ignore'
    errorStrategy { task.attempt <= 10  ? 'retry' : 'terminate' }
    conda "$TOOL_FOLDER/conda_env.yml"
    
    input:
    file "results/*" 

    output:
    file "merged_tsv/*" optional true

    """
    mkdir merged_tsv
    $params.PYTHONRUNTIME $TOOL_FOLDER/merged_results.py \
    results \
    --output_tsv_prefix merged_tsv/merged_tsv
    """
}



// Merging the JSON in rounds, 100 files at a time
process formatExtractedSpectraRounds {
    publishDir "$_publishdir/extracted", mode: 'copy'
    cache false
    errorStrategy 'ignore'

    conda "$TOOL_FOLDER/conda_env.yml"
    
    input:
    file "json/*" 

    output:
    file "extracted_mzML/*" optional true
    file "extracted_mgf/*" optional true
    file "extracted_json/*" optional true
    file "extracted_tsv/*" optional true 

    """
    mkdir extracted_mzML
    mkdir extracted_mgf
    mkdir extracted_json
    mkdir extracted_tsv
    $params.PYTHONRUNTIME $TOOL_FOLDER/merged_extracted.py \
    json \
    extracted_mzML \
    extracted_mgf \
    extracted_json \
    --output_tsv_prefix extracted_tsv/extracted_tsv \
    --naming $params.extractnaming
    """
}


// Extracting the spectra
// process formatExtractedSpectra {
//     publishDir "$params.publishdir/extracted", mode: 'copy'
//     cache false
//     errorStrategy 'ignore'

//     input:
//     file "input_merged.json" from _query_extract_results_merged_ch

//     output:
//     file "extracted_mzML" optional true
//     file "extracted_mgf" optional true
//     file "extracted.tsv" optional true
//     file "extracted_json" optional true into _extracted_json_ch

//     """
//     mkdir extracted_mzML
//     mkdir extracted_mgf
//     mkdir extracted_json
//     $params.PYTHONRUNTIME $TOOL_FOLDER/merged_extracted.py \
//     input_merged.json \
//     extracted_mzML \
//     extracted_mgf \
//     extracted_json \
//     extracted.tsv 
//     """
// }

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



process summarizeResults {
    publishDir "$_publishdir/summary", mode: 'copy'
    cache false
    errorStrategy 'ignore'

    conda "$TOOL_FOLDER/conda_env.yml"

    input:
    file(merged_results)

    output:
    file "summary.html" optional true

    """
    $params.PYTHONRUNTIME $TOOL_FOLDER/summarize_results.py \
    $merged_results \
    summary.html
    """
}



workflow {
    _spectra_ch = Channel.empty()
    _spectra_ch = _spectra_ch.concat(Channel.fromPath( params.input_spectra + "/**.mzML" ))
    _spectra_ch = _spectra_ch.concat(Channel.fromPath( params.input_spectra + "/**.mzml" ))
    _spectra_ch = _spectra_ch.concat(Channel.fromPath( params.input_spectra + "/**.mzXML" ))
    _spectra_ch = _spectra_ch.concat(Channel.fromPath( params.input_spectra + "/**.mzxml" ))
    _spectra_ch = _spectra_ch.concat(Channel.fromPath( params.input_spectra + "/**.MGF" ))
    _spectra_ch = _spectra_ch.concat(Channel.fromPath( params.input_spectra + "/**.mgf" ))
    _spectra_ch = _spectra_ch.concat(Channel.fromPath( params.input_spectra + "/**.json" ))
    
    //_spectra_ch = Channel.fromPath( params.input_spectra ) // This is the old code when we pass it a path to a glob of files
    
    _spectra_ch3 = _spectra_ch.map { file -> tuple(file, file.toString().replaceAll("/", "_").replaceAll(" ", "_"), file) }

    if(params.parallel_files == "YES"){
        (_query_results_ch, _query_extract_results_ch) = queryData(_spectra_ch3)
    }
    else{
        (_query_results_ch, _query_extract_results_ch) = queryData2(_spectra_ch3)
    }

    _merged_temp_summary_ch = formatResultsMergeRounds(_query_results_ch.collate( 100 ))
 
    _query_results_merged_ch = _merged_temp_summary_ch.collectFile(name: "merged_query_results.tsv", storeDir: "$_publishdir/msql", keepHeader: true)


    if(params.extract == "YES"){
        (_, _, _, _extracted_summary_ch) = formatExtractedSpectraRounds(_query_extract_results_ch.collate( 100 ))

        // Once we've done this, then we'lll do the actual merge
        _extracted_summary_ch.collectFile(name: "extracted.tsv", storeDir: "$_publishdir/extracted", keepHeader: true)
    }

    summarizeResults(_query_results_merged_ch)
}