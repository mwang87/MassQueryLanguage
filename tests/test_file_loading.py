import sys
import os

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from massql import msql_fileloading

import json
import pytest

def test_improper_file():
    with pytest.raises(Exception):
        msql_fileloading.load_file('file.cdf')

def test_gnps_library_loading():
    ms1_df, ms2_df = msql_fileloading.load_data("tests/data/gnps-library.json")
    print(ms2_df[ms2_df["scan"] == "CCMSLIB00000072227"])
    assert(len(ms2_df[ms2_df["scan"] == "CCMSLIB00000072227"]) > 300)