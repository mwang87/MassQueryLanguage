import json
import os
import pymzml
import pandas as pd
import numpy as np
from tqdm import tqdm
from matchms.importing import load_from_mgf
from pyteomics import mzxml


def load_data(input_filename, cache=False):
    """
    Loading data generically

    Args:
        input_filename ([type]): [description]
        cache (bool, optional): [description]. Defaults to False.

    Returns:
        [type]: [description]
    """
    if cache:
        ms1_filename = input_filename + "_ms1.msql.feather"
        ms2_filename = input_filename + "_ms2.msql.feather"

        if os.path.exists(ms1_filename) or os.path.exists(ms2_filename):
            try:
                ms1_df = pd.read_feather(ms1_filename)
            except:
                ms1_df = pd.DataFrame()
            try:
                ms2_df = pd.read_feather(ms2_filename)
            except:
                ms2_df = pd.DataFrame()

            return ms1_df, ms2_df

    # Actually loading
    if input_filename[-5:] == ".mzML":
        ms1_df, ms2_df = _load_data_mzML(input_filename)

    if input_filename[-6:] == ".mzXML":
        ms1_df, ms2_df = _load_data_mzXML(input_filename)
    
    if input_filename[-5:] == ".json":
        ms1_df, ms2_df = _load_data_gnps_json(input_filename)
    
    if input_filename[-4:] == ".mgf":
        ms1_df, ms2_df = _load_data_mgf(input_filename)

    # Saving Cache
    if cache:
        ms1_filename = input_filename + "_ms1.msql.feather"
        ms2_filename = input_filename + "_ms2.msql.feather"

        if not (os.path.exists(ms1_filename) or os.path.exists(ms2_filename)):
            try:
                ms1_df.to_feather(ms1_filename)
            except:
                pass

            try:
                ms2_df.to_feather(ms2_filename)
            except:
                pass

    return ms1_df, ms2_df

def _load_data_mgf(input_filename):
    file = load_from_mgf(input_filename)

    ms2mz_list = []
    for spectrum in file:
        if len(spectrum.peaks.mz) == 0:
            continue

        mz_list = list(spectrum.peaks.mz)
        i_list = list(spectrum.peaks.intensities)
        i_max = max(i_list)

        for i in range(len(mz_list)):
            peak_dict = {}
            peak_dict["i"] = i_list[i]
            peak_dict["i_norm"] = i_list[i] / i_max
            peak_dict["mz"] = mz_list[i]
            peak_dict["scan"] = spectrum.metadata["scans"]
            peak_dict["rt"] = spectrum.metadata["rtinseconds"]
            peak_dict["precmz"] = spectrum.metadata["pepmass"][0]
            peak_dict["ms1scan"] = 0

            ms2mz_list.append(peak_dict)

    # Turning into pandas data frames
    ms1_df = pd.DataFrame([peak_dict])
    ms2_df = pd.DataFrame(ms2mz_list)

    return ms1_df, ms2_df

def _load_data_gnps_json(input_filename):
    all_spectra = json.loads(open(input_filename).read())

    ms1_df_list = []
    ms2_df_list = []

    for spectrum in tqdm(all_spectra):
        peaks = json.loads(spectrum["peaks_json"])
        peaks = [peak for peak in peaks if peak[1] > 0]
        if len(peaks) == 0:
            continue
        i_max = max([peak[1] for peak in peaks])
        if i_max == 0:
            continue

        ms2mz_list = []

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
        if len(ms2mz_list) > 0:
            ms2_df = pd.DataFrame(ms2mz_list)
            ms2_df_list.append(ms2_df)
            
            ms1_df = pd.DataFrame([peak_dict])
            ms1_df_list.append(ms1_df)

    # Merging
    ms1_df = pd.concat(ms1_df_list).reset_index()
    ms2_df = pd.concat(ms2_df_list).reset_index()

    return ms1_df, ms2_df

def _load_data_mzXML(input_filename):
    ms1mz_list = []
    ms2mz_list = []
    previous_ms1_scan = 0

    with mzxml.read(input_filename) as reader:
        for spectrum in reader:
            if len(spectrum["intensity array"]) == 0:
                continue
                
            mz_list = list(spectrum["m/z array"])
            i_list = list(spectrum["intensity array"])
            i_max = max(i_list)

            mslevel = spectrum["msLevel"]
            if mslevel == 1:
                for i in range(len(mz_list)):
                    peak_dict = {}
                    peak_dict["i"] = i_list[i]
                    peak_dict["i_norm"] = i_list[i] / i_max
                    peak_dict["mz"] = mz_list[i]
                    peak_dict["scan"] = spectrum["id"]
                    peak_dict["rt"] = spectrum["retentionTime"]

                    ms1mz_list.append(peak_dict)

                    previous_ms1_scan = spectrum["id"]

            if mslevel == 2:
                msn_mz = spectrum["precursorMz"][0]["precursorMz"]
                for i in range(len(mz_list)):
                    peak_dict = {}
                    peak_dict["i"] = i_list[i]
                    peak_dict["i_norm"] = i_list[i] / i_max
                    peak_dict["mz"] = mz_list[i]
                    peak_dict["scan"] = spectrum["id"]
                    peak_dict["rt"] = spectrum["retentionTime"]
                    peak_dict["precmz"] = msn_mz
                    peak_dict["ms1scan"] = previous_ms1_scan

                    ms2mz_list.append(peak_dict)

    # Turning into pandas data frames
    ms1_df = pd.DataFrame(ms1mz_list)
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

    ms1_df_list = []
    ms2_df_list = []
    previous_ms1_scan = 0

    for i, spec in tqdm(enumerate(run)):
        ms1mz_list = []
        ms2mz_list = []

        # Getting RT
        rt = spec.scan_time_in_minutes()

        # Getting peaks
        peaks = spec.peaks("raw")

        # Filtering out zero rows
        peaks = peaks[~np.any(peaks < 1.0, axis=1)]

        # Sorting by intensity
        peaks = peaks[peaks[:, 1].argsort()]

        #print(spec.ms_level, len(peaks))

        if spec.ms_level == 2:
            # Getting top 1000
            peaks = peaks[-1000:]

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
        if len(ms1mz_list) > 0:
            ms1_df = pd.DataFrame(ms1mz_list)
            ms1_df_list.append(ms1_df)
        
        if len(ms2mz_list) > 0:
            ms2_df = pd.DataFrame(ms2mz_list)
            ms2_df_list.append(ms2_df)

    if len(ms1_df_list) > 0:
        ms1_df = pd.concat(ms1_df_list).reset_index()
    else:
        ms1_df = pd.DataFrame()

    if len(ms2_df_list) > 0:
        ms2_df = pd.concat(ms2_df_list).reset_index()
    else:
        ms2_df = pd.DataFrame()

    return ms1_df, ms2_df

