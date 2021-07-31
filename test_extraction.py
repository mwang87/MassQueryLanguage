import msql_extract
import msql_parser
import msql_engine
import msql_extract
import msql_translator
import msql_visualizer
import msql_fileloading
import json
import pytest

def test_extract():
    query = "QUERY scaninfo(MS2DATA)"
    results_df = msql_engine.process_query(query, "test/GNPS00002_A3_p.mzML")
    print(results_df)

    assert(len(results_df) > 1)
    results_df["filename"] = "GNPS00002_A3_p.mzML"

    msql_extract._extract_spectra(results_df, "test", output_json_filename="test.json")

def test_extract_mzXML():
    query = "QUERY scaninfo(MS1DATA)"
    results_df = msql_engine.process_query(query, "test/T04251505.mzXML")
    print(results_df)

    assert(len(results_df) > 1)
    results_df = results_df[:5]

    results_df["filename"] = "T04251505.mzXML"

    print("Extracting", len(results_df))
    msql_extract._extract_spectra(results_df, "test", output_json_filename="test.json")
    

def main():
    #test_extract()
    test_extract_mzXML()

if __name__ == "__main__":
    main()