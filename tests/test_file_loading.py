import sys
import os

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from massql import msql_fileloading

import json
import pytest
import time

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
    ms1_df, ms2_df = msql_fileloading.load_data("tests/data/T04251505.mzXML", cache=None)

def test_mgf_load():
    ms1_df, ms2_df = msql_fileloading.load_data("tests/data/specs_ms.mgf", cache=None)

def test_mzml_mobility_load():
    ms1_df, ms2_df = msql_fileloading.load_data("tests/data/meoh_water_ms2_1_31_1_395.mzML", cache=None)
    assert("mobility" in ms2_df)
    assert(max(ms2_df["rt"]) > 0)

def test_mzml_rt_seconds():
    ms1_df, ms2_df = msql_fileloading.load_data("tests/data/1810E-II.mzML", cache=None)
    print(ms2_df)
    assert(max(ms2_df["rt"]) < 60)

def test_waters_load():
    # This has UV spectra in it, we need to handle that gracefully
    ms1_df, ms2_df = msql_fileloading.load_data("tests/data/GT15A.mzML", cache=None)
    

def test_cache_feather():
    # Measure start time
    start_time = time.time()
    msql_fileloading.load_data("tests/data/JB_182_2_fe.mzML", cache="feather")
    msql_fileloading.load_data("tests/data/T04251505.mzXML", cache="feather")
    msql_fileloading.load_data("tests/data/meoh_water_ms2_1_31_1_395.mzML", cache="feather")
    # Measure end time
    end_time = time.time()
    print("Feather time: ", end_time - start_time)

def test_nocache():
    # Measure start time
    start_time = time.time()
    msql_fileloading.load_data("tests/data/JB_182_2_fe.mzML", cache=None)
    msql_fileloading.load_data("tests/data/T04251505.mzXML", cache=None)
    msql_fileloading.load_data("tests/data/meoh_water_ms2_1_31_1_395.mzML", cache=None)
    # Measure end time
    end_time = time.time()
    print("No cache time: ", end_time - start_time)

def test_cache_filename():
    input_filename = "tests/data/JB_182_2_fe.mzML"
    ms1_filename, ms2_filename = msql_fileloading._determine_feather_cache_filename(input_filename)
    assert(ms1_filename == "tests/data/JB_182_2_fe.mzML_ms1.msql.feather")

    ms1_filename, ms2_filename = msql_fileloading._determine_feather_cache_filename(input_filename, cache_file="cache_file")

    ms1_filename, ms2_filename = msql_fileloading._determine_feather_cache_filename(input_filename, cache_dir="cache_file")
    print(ms1_filename, ms2_filename)


def main():
    #test_mzml_load()
    #test_mzml_mobility_load()
    #test_mzml_rt_seconds()
    #test_waters_load()
    #test_cache_feather()
    #test_nocache()
    #test_cache_filename()
    test_mgf_load()
    

if __name__ == "__main__":
    main()
