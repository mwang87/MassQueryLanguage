run_test:
	nextflow run workflow.nf

run_resume_test:
	nextflow run workflow.nf --resume

cluster_test:
	nextflow run extract_data.nf -c cluster.config \
        --input_spectra="/data/massive/MSV000082622/ccms_peak/**.mzML" \
        --outdir="./nf_MSV000082622" \
        -with-trace -resume