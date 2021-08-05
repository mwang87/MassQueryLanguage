import msql_parser
import msql_engine
import msql_translator
import msql_visualizer
import msql_fileloading
import json
import pytest

def test_visualize():
    #query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=177 AND MS2PROD=270 AND MS2NL=163"
    #query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=X+14"
    #query = "QUERY scaninfo(MS2DATA) WHERE MS1MZ=X AND MS1MZ=X+14"
    query = "QUERY scaninfo(MS1DATA) WHERE \
            MS1MZ=X-2:INTENSITYMATCH=Y*0.063:INTENSITYMATCHPERCENT=25 \
            AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE"

    ms1_fig, ms2_fig = msql_visualizer.visualize_query(query)
    ms2_fig.write_image("test_ms2_visualize.png", engine="kaleido")
    ms1_fig.write_image("test_ms1_visualize.png", engine="kaleido")

    
def main():
    test_visualize()

if __name__ == "__main__":
    main()
