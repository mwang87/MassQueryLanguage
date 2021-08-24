import msql_extract
import msql_parser
import msql_engine
import msql_extract
import msql_translator
import msql_visualizer
import msql_fileloading
import json
import pytest

def test_improper_file():
    with pytest.raises(Exception):
        msql_fileloading.load_file('file.cdf')