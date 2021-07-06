nextflow run workflow.nf -c cluster.config \
        --input_spectra="./repo_data_qexactive/**.mzML" \
        --query="$1" \
        --publishdir="$2" \
        --parallel_files="YES" \
        --parallel_query="YES" \
        -with-trace -resume