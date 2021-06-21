import json
import pymzml
import pandas as pd
import numpy as np
from tqdm import tqdm
from pyteomics import mgf

def _load_data_mgf(input_filename):
    reader = mgf.read(input_filename)

    ms2mz_list = []
    for spectrum in reader:
        if len(spectrum["intensity array"]) == 0:
            continue
    
        mz_list = list(spectrum["m/z array"])
        i_list = list(spectrum["intensity array"])
        i_max = max(i_list)

        for i in range(len(mz_list)):
            peak_dict = {}
            peak_dict["i"] = i_list[i]
            peak_dict["i_norm"] = i_list[i] / i_max
            peak_dict["mz"] = mz_list[i]
            peak_dict["scan"] = spectrum["params"]["scans"]
            peak_dict["rt"] = spectrum["params"]["rtinseconds"]
            peak_dict["precmz"] = spectrum["params"]["pepmass"][0]
            peak_dict["ms1scan"] = 0

            ms2mz_list.append(peak_dict)

    # Turning into pandas data frames
    ms1_df = pd.DataFrame([peak_dict])
    ms2_df = pd.DataFrame(ms2mz_list)

    return ms1_df, ms2_df

def _load_data_gnps_json(input_filename):
    all_spectra = json.loads(open(input_filename).read())

    ms2mz_list = []

    for spectrum in all_spectra:
        peaks = json.loads(spectrum["peaks_json"])
        if len(peaks) == 0:
            continue
        i_max = max([peak[1] for peak in peaks])
        if i_max == 0:
            continue

        for peak in peaks:
            peak_dict = {}
            peak_dict["i"] = peak[1]
            peak_dict["i_norm"] = peak[1] / i_max
            peak_dict["mz"] = peak[0]
            peak_dict["scan"] = spectrum["spectrum_id"]
            peak_dict["rt"] = 0
            peak_dict["precmz"] = spectrum["Precursor_MZ"]
            peak_dict["ms1scan"] = 0

        ms2mz_list.append(peak_dict)

    # Turning into pandas data frames
    ms1_df = pd.DataFrame([peak_dict])
    ms2_df = pd.DataFrame(ms2mz_list)

    return ms1_df, ms2_df
    

def _load_data_mzML(input_filename):
    MS_precisions = {
        1: 5e-6,
        2: 20e-6,
        3: 20e-6,
        4: 20e-6,
        5: 20e-6,
        6: 20e-6,
        7: 20e-6,
    }
    run = pymzml.run.Reader(input_filename, MS_precisions=MS_precisions)

    ms1mz_list = []
    ms2mz_list = []
    previous_ms1_scan = 0

    for i, spec in tqdm(enumerate(run)):
        # Getting RT
        rt = spec.scan_time_in_minutes()

        # Getting peaks
        peaks = spec.peaks("raw")

        # Filtering out zero rows
        peaks = peaks[~np.any(peaks < 1.0, axis=1)]

        # Sorting by intensity
        peaks = peaks[peaks[:, 1].argsort()]

        # Getting top 1000
        #peaks = peaks[-1000:]

        if len(peaks) == 0:
            continue

        mz, intensity = zip(*peaks)

        mz_list = list(mz)
        i_list = list(intensity)
        i_max = max(i_list)
        
        if spec.ms_level == 1:
            for i in range(len(mz_list)):
                peak_dict = {}
                peak_dict["i"] = i_list[i]
                peak_dict["i_norm"] = i_list[i] / i_max
                peak_dict["mz"] = mz_list[i]
                peak_dict["scan"] = spec.ID
                peak_dict["rt"] = rt

                ms1mz_list.append(peak_dict)

                previous_ms1_scan = spec.ID

        if spec.ms_level == 2:
            msn_mz = spec.selected_precursors[0]["mz"]
            for i in range(len(mz_list)):
                peak_dict = {}
                peak_dict["i"] = i_list[i]
                peak_dict["i_norm"] = i_list[i] / i_max
                peak_dict["mz"] = mz_list[i]
                peak_dict["scan"] = spec.ID
                peak_dict["rt"] = rt
                peak_dict["precmz"] = msn_mz
                peak_dict["ms1scan"] = previous_ms1_scan

                ms2mz_list.append(peak_dict)

    # Turning into pandas data frames
    ms1_df = pd.DataFrame(ms1mz_list)
    ms2_df = pd.DataFrame(ms2mz_list)

    return ms1_df, ms2_df

