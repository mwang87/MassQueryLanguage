nextflow run workflow.nf -c cluster.config \
        --input_spectra="/data/massive-ro/$1/ccms_peak/**.mzML" \
        --publishdir="./nf_$1" \
		--parallel_files="YES" \
        -with-trace -resume