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

def test_mzml_load():
    print("Loading pymzML")
    ms1_df, ms2_df = msql_fileloading._load_data_mzML2("tests/data/JB_182_2_fe.mzML")
    print(ms2_df)

    assert(max(ms2_df["rt"]) > 0)

    print("Loading Pyteomics")
    ms1_df, ms2_df = msql_fileloading._load_data_mzML_pyteomics("tests/data/JB_182_2_fe.mzML")
    print(ms2_df)

    assert(max(ms2_df["rt"]) > 0)


def test_mzxml_load():
    ms1_df, ms2_df = msql_fileloading.load_data("tests/data/T04251505.mzXML", cache=False)

def test_mgf_load():
    ms1_df, ms2_df = msql_fileloading.load_data("tests/data/specs_ms.mgf", cache=False)

def test_mzml_mobility_load():
    ms1_df, ms2_df = msql_fileloading.load_data("tests/data/meoh_water_ms2_1_31_1_395.mzML", cache=False)
    assert("mobility" in ms2_df)
    assert(max(ms2_df["rt"]) > 0)

def main():
    #test_mzml_load()
    test_mzml_mobility_load()

if __name__ == "__main__":
    main()
