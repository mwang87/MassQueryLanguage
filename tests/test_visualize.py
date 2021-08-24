import sys
import os

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from massql import msql_visualizer

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

def test_visualize_xrange():
    query = "QUERY scaninfo(MS1DATA) WHERE \
            MS1MZ=X-2:INTENSITYMATCH=Y*0.063:INTENSITYMATCHPERCENT=25 \
            AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE AND \
            X=range(min=100, max=500)"

    ms1_fig, ms2_fig = msql_visualizer.visualize_query(query)
    ms2_fig.write_image("test_ms2_visualize.png", engine="kaleido")
    ms1_fig.write_image("test_ms1_visualize.png", engine="kaleido")

def test_visualize_y_set():
    query = "QUERY scaninfo(MS1DATA) WHERE \
            MS1MZ=X-2:INTENSITYMATCH=Y*0.063:INTENSITYMATCHPERCENT=25 \
            AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE"

    ms1_fig, ms2_fig = msql_visualizer.visualize_query(query, variable_y=0.1)
    ms1_fig.write_image("test_ms1_visualize.png", engine="kaleido")
    open("test_ms1_visualize.html", 'w').write(ms1_fig.to_html(full_html=False, include_plotlyjs='cdn'))

def test_visualize_usi():
    query = "QUERY scaninfo(MS1DATA) WHERE MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE:INTENSITYPERCENT=5 \
            AND \
            MS1MZ=X+1:INTENSITYMATCH=Y*0.4:INTENSITYMATCHPERCENT=70 AND MS1MZ=X+1.998:INTENSITYMATCH=Y*0.446:INTENSITYMATCHPERCENT=30:TOLERANCEPPM=10 AND MS2PREC=X"
    
    ms1_usi = "mzspec:MSV000085669:ccms_peak/mzML_ph5/std_mix_100-mixed-metal_2_ph8.mzML:scan:1380"

    import requests
    r = requests.get("https://metabolomics-usi.ucsd.edu/json/?usi1={}".format(ms1_usi))
    ms1_peaks = r.json()["peaks"]
    

    ms1_fig, ms2_fig = msql_visualizer.visualize_query(query, variable_x=662.27, variable_y=0.0436, ms1_peaks=ms1_peaks)
    ms1_fig.write_image("test_ms1_visualize.png", engine="kaleido")
    open("test_ms1_visualize.html", 'w').write(ms1_fig.to_html(full_html=False, include_plotlyjs='cdn'))
    
def main():
    #test_visualize_y_set()
    test_visualize_xrange()
    #test_visualize_usi()

if __name__ == "__main__":
    main()
