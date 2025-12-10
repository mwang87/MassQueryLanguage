# Testing

test_parse:
	pytest -vv --cov=massql ./tests/test_parse.py

test_translate:
	pytest -vv --cov=massql ./tests/test_translate.py

test_extraction:
	pytest -vv --cov=massql ./tests/test_extraction.py

test_visualize:
	pytest -vv --cov=massql ./tests/test_visualize.py

test_fileloading:
	pytest -vv --cov=massql ./tests/test_file_loading.py

test_query:
	pytest -vv --cov=massql ./tests/test_query.py  -n 4

test_full:
	pytest -vv --cov=massql ./tests/ -n 8

# test_full_parallel:
# 	pytest -vv test.py test_parse.py test_extraction.py -n 6

# test_specific:
# 	pytest --capture=tee-sys -vv test.py::test_min_intensitypercent
# 	pytest --capture=tee-sys -vv test.py::test_query

deploy_clean:
	rm build/ dist/ massql.egg-info -rf

deploy_pypi:
	python -m build --sdist --wheel .
	twine upload dist/*

specific_pytest:
	#pytest -vv --cov=massql ./tests/test_extraction.py::test_extract_MGF
	python ./tests/test_extraction.py