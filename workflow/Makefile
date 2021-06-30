run_test:
	nextflow run workflow.nf

run_resume_test:
	nextflow run workflow.nf --resume

cluster_test:
	nextflow run workflow.nf -c cluster.config \
        --input_spectra="/data/massive/MSV000082622/ccms_peak/**.mzML" \
        --publishdir="./nf_MSV000082622" \
		--parallel_files="YES" \
        -with-trace -resume