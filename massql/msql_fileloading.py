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
    if input_filename[-5:].lower() == ".mzml":
        #ms1_df, ms2_df = _load_data_mzML(input_filename)
        ms1_df, ms2_df = _load_data_mzML2(input_filename)

    elif input_filename[-6:].lower() == ".mzxml":
        ms1_df, ms2_df = _load_data_mzXML(input_filename)
    
    elif input_filename[-5:] == ".json":
        ms1_df, ms2_df = _load_data_gnps_json(input_filename)
    
    elif input_filename[-4:].lower() == ".mgf":
        ms1_df, ms2_df = _load_data_mgf(input_filename)

    elif input_filename[-4:].lower() == ".txt":
        ms1_df, ms2_df = _load_data_txt(input_filename)
    
    else:
        print("Cannot Load File Extension")
        raise Exception("File Format Not Supported")


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
    for i, spectrum in enumerate(file):
        if len(spectrum.peaks.mz) == 0:
            continue

        mz_list = list(spectrum.peaks.mz)
        i_list = list(spectrum.peaks.intensities)
        i_max = max(i_list)
        i_sum = sum(i_list)

        for i in range(len(mz_list)):
            if i_list[i] == 0:
                continue

            peak_dict = {}
            peak_dict["i"] = i_list[i]
            peak_dict["i_norm"] = i_list[i] / i_max
            peak_dict["i_tic_norm"] = i_list[i] / i_sum
            peak_dict["mz"] = mz_list[i]

            # Handling malformed mgf files
            try:
                peak_dict["scan"] = spectrum.metadata["scans"]
            except:
                peak_dict["scan"] = i + 1
            try:
                peak_dict["rt"] = float(spectrum.metadata["rtinseconds"]) / 60
            except:
                peak_dict["rt"] = 0
            try:
                peak_dict["precmz"] = float(spectrum.metadata["pepmass"][0])
            except:
                peak_dict["precmz"] = 0

            peak_dict["ms1scan"] = 0
            peak_dict["charge"] = 1 # TODO: Add Charge Correctly here
            peak_dict["polarity"] = 1 # TODO: Add Polarity Correctly here

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
        # Skipping spectra bigger than 1MB of peaks
        if len(spectrum["peaks_json"]) > 1000000:
            continue

        peaks = json.loads(spectrum["peaks_json"])
        peaks = [peak for peak in peaks if peak[1] > 0]
        if len(peaks) == 0:
            continue
        i_max = max([peak[1] for peak in peaks])
        i_sum = sum([peak[1] for peak in peaks])
        if i_max == 0:
            continue

        ms2mz_list = []

        for peak in peaks:
            peak_dict = {}
            peak_dict["i"] = peak[1]
            peak_dict["i_norm"] = peak[1] / i_max
            peak_dict["i_tic_norm"] = peak[1] / i_sum
            peak_dict["mz"] = peak[0]
            peak_dict["scan"] = spectrum["spectrum_id"]
            peak_dict["rt"] = 0
            peak_dict["precmz"] = float(spectrum["Precursor_MZ"])
            peak_dict["ms1scan"] = 0
            peak_dict["charge"] = 1 # TODO: Add Charge Correctly here
            peak_dict["polarity"] = 1 # TODO: Add Polarity Correctly here

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
        for spectrum in tqdm(reader):
            if len(spectrum["intensity array"]) == 0:
                continue
                
            mz_list = list(spectrum["m/z array"])
            i_list = list(spectrum["intensity array"])
            i_max = max(i_list)
            i_sum = sum(i_list)

            mslevel = spectrum["msLevel"]
            if mslevel == 1:
                for i in range(len(mz_list)):
                    peak_dict = {}
                    peak_dict["i"] = i_list[i]
                    peak_dict["i_norm"] = i_list[i] / i_max
                    peak_dict["i_tic_norm"] = i_list[i] / i_sum
                    peak_dict["mz"] = mz_list[i]
                    peak_dict["scan"] = spectrum["id"]
                    peak_dict["rt"] = spectrum["retentionTime"]
                    peak_dict["polarity"] = _determine_scan_polarity_mzXML(spectrum)

                    ms1mz_list.append(peak_dict)

                    previous_ms1_scan = spectrum["id"]

            if mslevel == 2:
                msn_mz = spectrum["precursorMz"][0]["precursorMz"]
                msn_charge = 0

                if "precursorCharge" in spectrum["precursorMz"][0]:
                    msn_charge = spectrum["precursorMz"][0]["precursorCharge"]
                    
                for i in range(len(mz_list)):
                    peak_dict = {}
                    peak_dict["i"] = i_list[i]
                    peak_dict["i_norm"] = i_list[i] / i_max
                    peak_dict["i_tic_norm"] = i_list[i] / i_sum
                    peak_dict["mz"] = mz_list[i]
                    peak_dict["scan"] = spectrum["id"]
                    peak_dict["rt"] = spectrum["retentionTime"]
                    peak_dict["precmz"] = msn_mz
                    peak_dict["ms1scan"] = previous_ms1_scan
                    peak_dict["charge"] = msn_charge
                    peak_dict["polarity"] = _determine_scan_polarity_mzXML(spectrum)

                    ms2mz_list.append(peak_dict)

    # Turning into pandas data frames
    ms1_df = pd.DataFrame(ms1mz_list)
    ms2_df = pd.DataFrame(ms2mz_list)

    return ms1_df, ms2_df


def _determine_scan_polarity_mzML(spec):
    """
    Gets an enum for positive and negative polarity

    Args:
        spec ([type]): [description]

    Returns:
        [type]: [description]
    """
    polarity = 0
    negative_polarity = spec["negative scan"]
    if negative_polarity is True:
        polarity = 2
    positive_polarity = spec["positive scan"]
    if positive_polarity is True:
        polarity = 1

    return polarity

def _determine_scan_polarity_mzXML(spec):
    polarity = 0
    if spec["polarity"] == "+":
        polarity = 1
    if spec["polarity"] == "-":
        polarity = 2
    return polarity

def _load_data_mzML2(input_filename):
    """This is a faster loading version, but a bit more memory intensive

    Args:
        input_filename ([type]): [description]

    Returns:
        [type]: [description]
    """    


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

    previous_ms1_scan = 0

    # MS1
    all_mz = []
    all_rt = []
    all_polarity = []
    all_i = []
    all_i_norm = []
    all_i_tic_norm = []
    all_scan = []

    # MS2
    all_msn_mz = []
    all_msn_rt = []
    all_msn_polarity = []
    all_msn_i = []
    all_msn_i_norm = []
    all_msn_i_tic_norm = []
    all_msn_scan = []
    all_msn_precmz = []
    all_msn_ms1scan = []
    all_msn_charge = []

    for i, spec in tqdm(enumerate(run)):
        # Getting RT
        rt = spec.scan_time_in_minutes()

        # Getting peaks
        peaks = spec.peaks("raw")

        # Filtering out zero rows
        peaks = peaks[~np.any(peaks < 1.0, axis=1)]

        if spec.ms_level == 2:
            if len(peaks) > 1000:
                # Sorting by intensity
                peaks = peaks[peaks[:,1].argsort()]

                # Getting top 1000
                peaks = peaks[-1000:]

        if len(peaks) == 0:
            continue
        
        mz, intensity = zip(*peaks)

        i_max = max(intensity)
        i_sum = sum(intensity)

        if spec.ms_level == 1:
            all_mz += list(mz)
            all_i += list(intensity)
            all_i_norm += list(intensity / i_max)
            all_i_tic_norm += list(intensity / i_sum)
            all_rt += len(mz) * [rt]
            all_scan += len(mz) * [spec.ID]
            all_polarity += len(mz) * [_determine_scan_polarity_mzML(spec)]

            previous_ms1_scan = spec.ID

        if spec.ms_level == 2:
            msn_mz = spec.selected_precursors[0]["mz"]
            charge = 0
            if "charge" in spec.selected_precursors[0]:
                charge = spec.selected_precursors[0]["charge"]

            all_msn_mz += list(mz)
            all_msn_i += list(intensity)
            all_msn_i_norm += list(intensity / i_max)
            all_msn_i_tic_norm += list(intensity / i_sum)
            all_msn_rt += len(mz) * [rt]
            all_msn_scan += len(mz) * [spec.ID]
            all_msn_polarity += len(mz) * [_determine_scan_polarity_mzML(spec)]
            all_msn_precmz += len(mz) * [msn_mz]
            all_msn_ms1scan += len(mz) * [previous_ms1_scan] 
            all_msn_charge += len(mz) * [charge]


    ms1_df = pd.DataFrame()
    if len(all_mz) > 0:
        ms1_df['i'] = all_i
        ms1_df['i_norm'] = all_i_norm
        ms1_df['i_tic_norm'] = all_i_tic_norm
        ms1_df['mz'] = all_mz
        ms1_df['scan'] = all_scan
        ms1_df['rt'] = all_rt
        ms1_df['polarity'] = all_polarity

    ms2_df = pd.DataFrame()
    if len(all_msn_mz) > 0:
        ms2_df['i'] = all_msn_i
        ms2_df['i_norm'] = all_msn_i_norm
        ms2_df['i_tic_norm'] = all_msn_i_tic_norm
        ms2_df['mz'] = all_msn_mz
        ms2_df['scan'] = all_msn_scan
        ms2_df['rt'] = all_msn_rt
        ms2_df["polarity"] = all_msn_polarity
        ms2_df["precmz"] = all_msn_precmz
        ms2_df["ms1scan"] = all_msn_ms1scan
        ms2_df["charge"] = all_msn_charge
    
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
        ms1_df = pd.DataFrame()
        ms2_df = pd.DataFrame()

        # Getting RT
        rt = spec.scan_time_in_minutes()

        # Getting peaks
        peaks = spec.peaks("raw")

        # Filtering out zero rows
        peaks = peaks[~np.any(peaks < 1.0, axis=1)]

        # Sorting by intensity
        peaks = peaks[peaks[:, 1].argsort()]

        if spec.ms_level == 2:
            # Getting top 1000
            peaks = peaks[-1000:]

        if len(peaks) == 0:
            continue

        mz, intensity = zip(*peaks)

        i_max = max(intensity)
        i_sum = sum(intensity)
        
        if spec.ms_level == 1:
            ms1_df['i'] = intensity
            ms1_df['i_norm'] = intensity / i_max
            ms1_df['i_tic_norm'] = intensity / i_sum
            ms1_df['mz'] = mz
            ms1_df['scan'] = spec.ID
            ms1_df['rt'] = rt
            ms1_df['polarity'] = _determine_scan_polarity_mzML(spec)
            
            previous_ms1_scan = spec.ID

        if spec.ms_level == 2:
            msn_mz = spec.selected_precursors[0]["mz"]
            charge = 0
            if "charge" in spec.selected_precursors[0]:
                charge = spec.selected_precursors[0]["charge"]

            ms2_df['i'] = intensity
            ms2_df['i_norm'] = intensity / i_max
            ms2_df['i_tic_norm'] = intensity / i_sum
            ms2_df['mz'] = mz
            ms2_df['scan'] = spec.ID
            ms2_df['rt'] = rt
            ms2_df["polarity"] = _determine_scan_polarity_mzML(spec)
            ms2_df["precmz"] = msn_mz
            ms2_df["ms1scan"] = previous_ms1_scan
            ms2_df["charge"] = charge

        # Turning into pandas data frames
        if len(ms1_df) > 0:
            ms1_df_list.append(ms1_df)
        
        if len(ms2_df) > 0:
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

def _load_data_txt(input_filename):
    # We are assuming whitespace separated columns, first is mz, second is intensity, and will be marked as MS1
    mz_list = []
    i_list = []
    for line in open(input_filename):
        cleaned_line = line.rstrip()
        if len(cleaned_line) == 0:
            continue
        mz, i = cleaned_line.split()

        mz_list.append(float(mz))
        i_list.append(float(i))
        
    ms1_df = pd.DataFrame()
    ms1_df['mz'] = mz_list
    ms1_df['i'] = i_list
    ms1_df['i_norm'] = ms1_df['i'] / max(ms1_df['i'])
    ms1_df['i_tic_norm'] = ms1_df['i'] / sum(ms1_df['i'])
    ms1_df['scan'] = 1
    ms1_df['rt'] = 0
    ms1_df['polarity'] = "Positive"

    print(ms1_df)

    return ms1_df, pd.DataFrame()
