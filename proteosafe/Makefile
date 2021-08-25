-include Makefile.credentials

test-manual-beta-msql-nf:
	python ./CCMS-Integration-Tests/workflow_integration/submit_test_job_batch.py \
	--credential_username ${CCMS_TESTUSER_USERNAME} \
	--credential_password ${CCMS_TESTUSER_PASSWORD} \
	--workflow_version ${WORKFLOW_VERSION} \
	--credential_server proteomics3.ucsd.edu \
	--workflow_task_file msql-nf/test-integration-workflow/test_tasks.csv

test-manual-gnps-msql-nf:
	python ./CCMS-Integration-Tests/workflow_integration/submit_test_job_batch.py \
	--credential_username ${CCMS_TESTUSER_USERNAME} \
	--credential_password ${CCMS_TESTUSER_PASSWORD} \
	--workflow_version ${WORKFLOW_VERSION} \
	--credential_server gnps.ucsd.edu \
	--workflow_task_file msql-nf/test-integration-workflow/test_tasks.csv