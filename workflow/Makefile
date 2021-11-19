run_test:
	nextflow run workflow.nf -c test.config

run_test_extract_original:
	nextflow run workflow.nf -c test.config --extractnaming="original"

run_test_no_extract:
	nextflow run workflow.nf --extract="No" -c test.config

run_resume_test:
	nextflow run workflow.nf --resume

# Running example with Iron
run_test_iron:
	nextflow run workflow.nf -c test.config --input_spectra="./test/isa_9_fe.mzML" --query="QUERY scaninfo(MS1DATA) WHERE MS1MZ=X-2:INTENSITYMATCH=Y*0.063:INTENSITYMATCHPERCENT=25 AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE:INTENSITYPERCENT=5 AND MS2PREC=X" --resume


cluster_test:
	nextflow run workflow.nf -c cluster.config \
        --input_spectra="/data/massive/MSV000082622/ccms_peak/**.mzML" \
        --publishdir="./nf_MSV000082622" \
		--parallel_files="YES" \
        -with-trace -resume

cluster_full:
	nextflow run workflow.nf -c cluster.config \
        --input_spectra="./repo_data/**.mzML" \
        --publishdir="./nf_output_repo_data" \
		--parallel_files="YES" \
        -with-trace -resume

cluster_full_qexactive:
	nextflow run workflow.nf -c cluster.config \
        --input_spectra="./repo_data_qexactive/**.mzML" \
        --publishdir="./nf_output_repo_data_qexactive" \
		--parallel_files="YES" \
        -with-trace -resume