

test_full:
	pytest -vv test.py

test_full_parallel:
	pytest -vv test.py test_parse.py test_extraction.py -n 6

test_specific:
	pytest --capture=tee-sys -vv test.py::test_min_intensitypercent
	pytest --capture=tee-sys -vv test.py::test_query
	