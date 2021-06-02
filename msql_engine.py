import msql_parser

import os
import pandas as pd
import pymzml
import numpy as np
import copy
import logging
from tqdm import tqdm

import ray

console = logging.StreamHandler()
console.setLevel(logging.INFO)


def DEBUG_MSG(msg):
    import sys

    print(msg, file=sys.stderr, flush=True)

def init_ray():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)

def _load_data(input_filename, cache=False):
    if cache:
        ms1_filename = input_filename + "_ms1.feather"
        ms2_filename = input_filename + "_ms2.feather"

        if os.path.exists(ms1_filename):
            ms1_df = pd.read_feather(ms1_filename)
            ms2_df = pd.read_feather(ms2_filename)

            return ms1_df, ms2_df

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

    for spec in run:
        # Getting RT
        rt = spec.scan_time_in_minutes()

        # Getting peaks
        peaks = spec.peaks("raw")

        # Filtering out zero rows
        peaks = peaks[~np.any(peaks < 1.0, axis=1)]

        # Sorting by intensity
        peaks = peaks[peaks[:, 1].argsort()]

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

    # Saving Cache
    if cache:
        ms1_filename = input_filename + "_ms1.feather"
        ms2_filename = input_filename + "_ms2.feather"

        if not os.path.exists(ms1_filename):
            ms1_df.to_feather(ms1_filename)
            ms2_df.to_feather(ms2_filename)

    return ms1_df, ms2_df


def _get_tolerance(qualifier, mz):
    if qualifier is None:
        return 0.1

    if "qualifierppmtolerance" in qualifier:
        ppm = qualifier["qualifierppmtolerance"]["value"]
        mz_tol = abs(ppm * mz / 1000000)
        return mz_tol

    if "qualifiermztolerance" in qualifier:
        return qualifier["qualifiermztolerance"]["value"]

    return 0.1

def _get_minintensity(qualifier):
    if qualifier is None:
        return 0, 0

    if "qualifierintensityvalue" in qualifier:
        return qualifier["qualifierintensityvalue"]["value"], 0

    if "qualifierintensitypercent" in qualifier:
        return 0, qualifier["qualifierintensitypercent"]["value"] / 100

    return 0, 0


def process_query(input_query, input_filename, path_to_grammar="msql.ebnf", cache=True):
    parsed_dict = msql_parser.parse_msql(input_query, path_to_grammar=path_to_grammar)

    return _evalute_variable_query(parsed_dict, input_filename, cache=cache)


def _evalute_variable_query(parsed_dict, input_filename, cache=True):
    # Lets check if there is a variable in here, the only one allowed is X
    for condition in parsed_dict["conditions"]:
        try:
            if "querytype" in condition["value"][0]:
                subquery_val_df = _evalute_variable_query(
                    condition["value"][0], input_filename, cache=cache
                )
                condition["value"] = list(
                    subquery_val_df["precmz"]
                )  # Flattening results
        except:
            pass

    # Here we will check if there is a variable in the expression
    has_variable = False
    for condition in parsed_dict["conditions"]:
        for value in condition["value"]:
            try:
                if "X" in value:
                    has_variable = True
                    break
            except TypeError:
                # This is when the target is actually a float
                pass
    
    all_concrete_queries = []
    if has_variable:
        DELTA_VAL = 0.1
        # Lets iterate through all values of the variable
        #MAX_MZ = 10
        #MAX_MZ = 200
        MAX_MZ = 1000

        for i in tqdm(range(int(MAX_MZ / DELTA_VAL))):
            x_val = i * DELTA_VAL + 150

            # Writing new query
            substituted_parse = copy.deepcopy(parsed_dict)

            for condition in substituted_parse["conditions"]:
                for i, value in enumerate(condition["value"]):
                    try:
                        if "X" in value:
                            if "+" in value:
                                new_value = x_val + float(value.split("+")[-1])
                            else:
                                new_value = x_val
                            # print("SUBSTITUTE", condition, value, i, new_value)
                            condition["value"][i] = new_value
                    except TypeError:
                        # This is when the target is actually a float
                        pass

            print(substituted_parse)
            all_concrete_queries.append(substituted_parse)
    else:
        all_concrete_queries.append(parsed_dict)
        

    # Perfoming the filtering of conditions
    results_ms1_list = []
    results_ms2_list = []

    # Ray Parallel Version
    if ray.is_initialized():
        ms1_df, ms2_df = _load_data(input_filename, cache=cache)
        futures = [_executeconditions_query_ray.remote(concrete_query, input_filename, ms1_input_df=ms1_df, ms2_input_df=ms2_df, cache=cache) for concrete_query in all_concrete_queries]
        all_ray_results = ray.get(futures)
        results_ms1_list, results_ms2_list = zip(*all_ray_results)
    else:
        # Serial Version
        for concrete_query in tqdm(all_concrete_queries):
            ms1_df, ms2_df = _executeconditions_query(concrete_query, input_filename, cache=cache)
            
            results_ms1_list.append(ms1_df)
            results_ms2_list.append(ms2_df)

    aggregated_ms1_df = pd.concat(results_ms1_list)
    aggregated_ms2_df = pd.concat(results_ms2_list)

    # reduce redundancy
    aggregated_ms1_df = aggregated_ms1_df.drop_duplicates()
    aggregated_ms2_df = aggregated_ms2_df.drop_duplicates()

    
    # Collating all results
    return _executecollate_query(parsed_dict, aggregated_ms1_df, aggregated_ms2_df)

@ray.remote
def _executeconditions_query_ray(parsed_dict, input_filename, ms1_input_df=None, ms2_input_df=None, cache=True):
    return _executeconditions_query(parsed_dict, input_filename, ms1_input_df=ms1_input_df, ms2_input_df=ms2_input_df, cache=cache)

def _executeconditions_query(parsed_dict, input_filename, ms1_input_df=None, ms2_input_df=None, cache=True):
    # This function attempts to find the data that the query specifies in the conditions
    #import json
    #print("parsed_dict", json.dumps(parsed_dict, indent=4))

    # Let's apply this to real data
    if ms1_input_df is None and ms2_input_df is None:
        ms1_df, ms2_df = _load_data(input_filename, cache=cache)
    else:
        ms1_df = ms1_input_df
        ms2_df = ms2_input_df

    # These are for the where clause
    for condition in parsed_dict["conditions"]:
        if not condition["conditiontype"] == "where":
            continue

        #logging.error("WHERE CONDITION", condition)

        # Filtering MS2 Product Ions
        if condition["type"] == "ms2productcondition":
            mz = condition["value"][0]
            mz_tol = _get_tolerance(condition.get("qualifiers", None), mz)
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            min_int, min_intpercent = _get_minintensity(condition.get("qualifiers", None))

            ms2_filtered_df = ms2_df[(ms2_df["mz"] > mz_min) & (ms2_df["mz"] < mz_max) & (ms2_df["i"] > min_int) & (ms2_df["i_norm"] > min_intpercent)]
            filtered_scans = set(ms2_filtered_df["scan"])
            ms2_df = ms2_df[ms2_df["scan"].isin(filtered_scans)]

            # Filtering the MS1 data now
            ms1_scans = set(ms2_df["ms1scan"])
            ms1_df = ms1_df[ms1_df["scan"].isin(ms1_scans)]

        # Filtering MS2 Precursor m/z
        if condition["type"] == "ms2precursorcondition":
            mz = condition["value"][0]
            mz_tol = 0.1
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol
            ms2_df = ms2_df[(ms2_df["precmz"] > mz_min) & (ms2_df["precmz"] < mz_max)]

        # Filtering MS2 Neutral Loss
        if condition["type"] == "ms2neutrallosscondition":
            mz = condition["value"][0]
            mz_tol = 0.1
            nl_min = mz - mz_tol
            nl_max = mz + mz_tol
            ms2_filtered_df = ms2_df[
                ((ms2_df["precmz"] - ms2_df["mz"]) > nl_min)
                & ((ms2_df["precmz"] - ms2_df["mz"]) < nl_max)
            ]
            filtered_scans = set(ms2_filtered_df["scan"])
            ms2_df = ms2_df[ms2_df["scan"].isin(filtered_scans)]

            # Filtering the MS1 data now
            ms1_scans = set(ms2_df["ms1scan"])
            ms1_df = ms1_df[ms1_df["scan"].isin(ms1_scans)]

        # finding MS1 peaks
        if condition["type"] == "ms1mzcondition":
            mz = condition["value"][0]
            mz_tol = 0.1
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            min_int, min_intpercent = _get_minintensity(condition.get("qualifiers", None))
            
            ms1_filtered_df = ms1_df[(ms1_df["mz"] > mz_min) & (ms1_df["mz"] < mz_max) & (ms1_df["i"] > min_int) & (ms1_df["i_norm"] > min_intpercent)]
            filtered_scans = set(ms1_filtered_df["scan"])
            ms1_df = ms1_df[ms1_df["scan"].isin(filtered_scans)]

    # These are for the where clause
    for condition in parsed_dict["conditions"]:
        if not condition["conditiontype"] == "filter":
            continue

        logging.error("FILTER CONDITION", condition)

        # filtering MS1 peaks
        if condition["type"] == "ms1mzcondition":
            mz = condition["value"][0]
            mz_tol = 0.1
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol
            ms1_df = ms1_df[(ms1_df["mz"] > mz_min) & (ms1_df["mz"] < mz_max)]
        
        if condition["type"] == "ms2productcondition":
            mz = condition["value"][0]
            mz_tol = _get_tolerance(condition.get("qualifiers", None), mz)
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            min_int, min_intpercent = _get_minintensity(condition.get("qualifiers", None))

            ms2_df = ms2_df[(ms2_df["mz"] > mz_min) & (ms2_df["mz"] < mz_max) & (ms2_df["i"] > min_int) & (ms2_df["i_norm"] > min_intpercent)]

    return ms1_df, ms2_df

def _executecollate_query(parsed_dict, ms1_df, ms2_df):
    # This function takes the dataframes from executing the conditions and returns the proper formatted version

    # collating the results
    if parsed_dict["querytype"]["function"] is None:
        if parsed_dict["querytype"]["datatype"] == "datams1data":
            return ms1_df
        if parsed_dict["querytype"]["datatype"] == "datams2data":
            return ms2_df
    else:
        print(parsed_dict["querytype"]["function"])
        # Applying function
        if parsed_dict["querytype"]["function"] == "functionscansum":

            # TODO: Fix how this scan is done so the result values for most things actually make sense
            if parsed_dict["querytype"]["datatype"] == "datams1data":
                ms1sum_df = ms1_df.groupby("scan").sum().reset_index()

                ms1_df = ms1_df.groupby("scan").first().reset_index()
                ms1_df["i"] = ms1sum_df["i"]

                return ms1_df
            if parsed_dict["querytype"]["datatype"] == "datams2data":
                ms2sum_df = ms2_df.groupby("scan").sum().reset_index()
                
                ms2_df = ms2_df.groupby("scan").first().reset_index()
                ms2_df["i"] = ms2sum_df["i"]

                return ms2_df

        if parsed_dict["querytype"]["function"] == "functionscanmz":
            result_df = pd.DataFrame()
            result_df["precmz"] = list(set(ms2_df["precmz"]))
            return result_df

        if parsed_dict["querytype"]["function"] == "functionscannum":
            result_df = pd.DataFrame()

            if parsed_dict["querytype"]["datatype"] == "datams1data":
                result_df["scan"] = list(set(ms1_df["scan"]))
            if parsed_dict["querytype"]["datatype"] == "datams2data":
                result_df["scan"] = list(set(ms2_df["scan"]))

            return result_df

        if parsed_dict["querytype"]["function"] == "functionscaninfo":
            result_df = pd.DataFrame()

            if parsed_dict["querytype"]["datatype"] == "datams1data":
                result_df = ms1_df.groupby("scan").first().reset_index()
                result_df = result_df[["scan", "rt"]]
            if parsed_dict["querytype"]["datatype"] == "datams2data":
                result_df = ms2_df.groupby("scan").first().reset_index()
                result_df = result_df[["scan", "precmz", "ms1scan", "rt"]]

            return result_df

        if parsed_dict["querytype"]["function"] == "functionscanrangesum":
            result_list = []

            if parsed_dict["querytype"]["datatype"] == "datams1data":
                ms1_df["bin"] = ms1_df["mz"].apply(lambda x: int(x / 0.1))
                all_bins = set(ms1_df["bin"])

                for bin in all_bins:
                    ms1_filtered_df = ms1_df[ms1_df["bin"] == bin]
                    ms1sum_df = ms1_filtered_df.groupby("scan").sum().reset_index()

                    ms1_filtered_df = (
                        ms1_filtered_df.groupby("scan").first().reset_index()
                    )
                    ms1_filtered_df["i"] = ms1sum_df["i"]

                    result_list.append(ms1_filtered_df)

                return pd.concat(result_list)
            if parsed_dict["querytype"]["datatype"] == "datams2data":
                ms2_df = ms2_df.groupby("scan").sum()

                ms2sum_df = ms2_df.groupby("scan").sum()
                ms2_df = ms2_df.groupby("scan").first().reset_index()
                ms2_df["i"] = ms2sum_df["i"]

                return ms2_df

        print("APPLYING FUNCTION")    
