

test_full:
	pytest -vv test.py
	
test_specific:
	pytest --capture=tee-sys -vv test.py::test_min_intensitypercent
	pytest --capture=tee-sys -vv test.py::test_query
	