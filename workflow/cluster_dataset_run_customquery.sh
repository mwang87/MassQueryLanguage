nextflow run workflow.nf -c cluster.config \
        --input_spectra="/data/massive-ro/$1/ccms_peak/**.mzML" \
		--parallel_files="YES" \
        --query="$2" \
        --publishdir="$3" \
        -with-trace -resume