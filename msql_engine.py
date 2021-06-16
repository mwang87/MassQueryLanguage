import msql_parser

import os
import pandas as pd
import pymzml
import numpy as np
import copy
import logging
from tqdm import tqdm

import ray
from py_expression_eval import Parser

math_parser = Parser()
console = logging.StreamHandler()
console.setLevel(logging.INFO)


def DEBUG_MSG(msg):
    import sys

    print(msg, file=sys.stderr, flush=True)

def init_ray():
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, object_store_memory=10000000000)

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

    for i, spec in enumerate(run):
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

def _get_ppm_tolerance(qualifiers):
    if qualifiers is None:
        return None

    if "qualifierppmtolerance" in qualifiers:
        ppm = qualifiers["qualifierppmtolerance"]["value"]
        return ppm

    return None

def _get_da_tolerance(qualifiers):
    if qualifiers is None:
        return None

    if "qualifiermztolerance" in qualifiers:
        return qualifiers["qualifiermztolerance"]["value"]

    return None

def _get_mz_tolerance(qualifiers, mz):
    if qualifiers is None:
        return 0.1

    if "qualifierppmtolerance" in qualifiers:
        ppm = qualifiers["qualifierppmtolerance"]["value"]
        mz_tol = abs(ppm * mz / 1000000)
        return mz_tol

    if "qualifiermztolerance" in qualifiers:
        return qualifiers["qualifiermztolerance"]["value"]

    return 0.1

def _get_minintensity(qualifier):
    """
    Returns absolute min and relative min

    Args:
        qualifier ([type]): [description]

    Returns:
        [type]: [description]
    """

    if qualifier is None:
        return 0, 0

    if "qualifierintensityvalue" in qualifier:
        return qualifier["qualifierintensityvalue"]["value"], 0

    if "qualifierintensitypercent" in qualifier:
        return 0, qualifier["qualifierintensitypercent"]["value"] / 100

    return 0, 0

def _get_intensitymatch_range(qualifiers, match_intensity):
    min_intensity = 0
    max_intensity = 0

    if "qualifierintensitytolpercent" in qualifiers:
        tolerance_percent = qualifiers["qualifierintensitytolpercent"]["value"]
        tolerance_value = float(tolerance_percent) / 100 * match_intensity
        
        min_intensity = match_intensity - tolerance_value
        max_intensity = match_intensity + tolerance_value

    return min_intensity, max_intensity



def _filter_intensitymatch(ms_filtered_df, register_dict, condition):
    if "qualifiers" in condition:
        if "qualifierintensitymatch" in condition["qualifiers"] and \
            "qualifierintensitytolpercent" in condition["qualifiers"]:
            qualifier_expression = condition["qualifiers"]["qualifierintensitymatch"]["value"]
            qualifier_variable = qualifier_expression[0] #TODO: This assumes the variable is the first character in the expression, likely a bad assumption

            grouped_df = ms_filtered_df.groupby("scan").sum().reset_index()
            filtered_grouped_scans = []
            for grouped_scan in grouped_df.to_dict(orient="records"):
                # Reading from the register
                key = "scan:{}:variable:{}".format(grouped_scan["scan"], qualifier_variable)

                if key in register_dict:
                    register_value = register_dict[key]                    
                    evaluated_new_expression = math_parser.parse(qualifier_expression).evaluate({
                        qualifier_variable : register_value
                    })

                    min_match_intensity, max_match_intensity = _get_intensitymatch_range(condition["qualifiers"], evaluated_new_expression)

                    scan_intensity = grouped_scan["i"]

                    if scan_intensity > min_match_intensity and \
                        scan_intensity < max_match_intensity:
                        filtered_grouped_scans.append(grouped_scan)
                else:
                    # Its not in the register, which means we don't find it
                    continue

            return pd.DataFrame(filtered_grouped_scans)

    return ms_filtered_df

def _set_intensity_register(ms_filtered_df, register_dict, condition):
    if "qualifiers" in condition:
        if "qualifierintensityreference" in condition["qualifiers"]:
            qualifier_variable = condition["qualifiers"]["qualifierintensitymatch"]["value"]

            grouped_df = ms_filtered_df.groupby("scan").sum().reset_index()
            for grouped_scan in grouped_df.to_dict(orient="records"):
                # Saving into the register
                key = "scan:{}:variable:{}".format(grouped_scan["scan"], qualifier_variable)
                register_dict[key] = grouped_scan["i"]
    return

def process_query(input_query, input_filename, path_to_grammar="msql.ebnf", cache=True, parallel=True):
    parsed_dict = msql_parser.parse_msql(input_query, path_to_grammar=path_to_grammar)

    return _evalute_variable_query(parsed_dict, input_filename, cache=cache, parallel=parallel)

def _determine_mz_max(mz, ppm_tol, da_tol):
    da_tol = da_tol if da_tol < 10000 else 0
    ppm_tol = ppm_tol if ppm_tol < 10000 else 0
    # We are going to make the bins half of the actual tolerance
    half_delta = max(mz * ppm_tol / 1000000, da_tol) / 2

    half_delta = half_delta if half_delta > 0 else 0.05

    return mz + half_delta

def _evalute_variable_query(parsed_dict, input_filename, cache=True, parallel=True):
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
    variable_properties = {}
    variable_properties["has_variable"] = False
    variable_properties["ppm_tolerance"] = 100000
    variable_properties["da_tolerance"] = 100000
    variable_properties["query_ms1"] = False
    variable_properties["query_ms2"] = False
    
    for condition in parsed_dict["conditions"]:
        for value in condition["value"]:
            try:
                # Checking if X is in any string
                if "X" in value[0]:
                    variable_properties["has_variable"] = True
                    #mz_tolerance = _get_mz_tolerance(condition.get("qualifiers", None), 1000000)

                    ppm_tolerance = _get_ppm_tolerance(condition.get("qualifiers", None))
                    da_tolerance = _get_da_tolerance(condition.get("qualifiers", None))

                    if da_tolerance is not None:
                        variable_properties["da_tolerance"] = min(variable_properties["da_tolerance"], da_tolerance)
                    if ppm_tolerance is not None:
                        variable_properties["ppm_tolerance"] = min(variable_properties["ppm_tolerance"], ppm_tolerance)                    
                    continue
            except TypeError:
                # This is when the target is actually a float
                pass

    ms1_df, ms2_df = _load_data(input_filename, cache=cache)

    # Here we are going to translate the variable query into a concrete query based upon the data
    all_concrete_queries = []
    if variable_properties["has_variable"]:
        # Here we could do a pre-query without any of the other conditions
        presearch_parse = copy.deepcopy(parsed_dict)
        non_variable_conditions = []
        for condition in presearch_parse["conditions"]:
            for value in condition["value"]:
                try:
                    # Checking if X is in any string
                    if "X" in value[0]:
                        continue
                except TypeError:
                    # This is when the target is actually a float
                    pass
                non_variable_conditions.append(condition)
        presearch_parse["conditions"] = non_variable_conditions
        ms1_df, ms2_df = _executeconditions_query(presearch_parse, input_filename, cache=cache)

        # Here we will start with the smallest mass and then go up
        masses_considered_df = pd.DataFrame()
        masses_considered_df["mz"] = pd.concat([ms1_df["mz"], ms2_df["mz"], ms2_df["precmz"]])
        masses_considered_df["mz_max"] = masses_considered_df["mz"].apply(lambda x: _determine_mz_max(x, variable_properties["ppm_tolerance"], variable_properties["da_tolerance"]))
        
        masses_considered_df = masses_considered_df.sort_values("mz")
        masses_list = masses_considered_df.to_dict(orient="records")

        running_max_mz = 0
        for masses_obj in tqdm(masses_list):
            if running_max_mz > masses_obj["mz"]:
                continue

            # Writing new query
            substituted_parse = copy.deepcopy(parsed_dict)
            mz_val = masses_obj["mz"]

            for condition in substituted_parse["conditions"]:
                for i, value in enumerate(condition["value"]):
                    try:
                        if "X" in value:
                            new_value = math_parser.parse(value).evaluate({
                                "X" : mz_val
                            })
                            condition["value"][i] = new_value
                    except TypeError:
                        # This is when the target is actually a float
                        pass

            substituted_parse["comment"] = str(mz_val)
            all_concrete_queries.append(substituted_parse)
            
            # Let's consider this mz
            running_max_mz = masses_obj["mz_max"]


        # DELTA_VAL = 0.1
        # # Lets iterate through all values of the variable
        # #MAX_MZ = 10
        # #MAX_MZ = 200
        # MAX_MZ = 1000

        # for i in tqdm(range(int(MAX_MZ / DELTA_VAL))):
        #     x_val = i * DELTA_VAL + 150

        #     # Writing new query
        #     substituted_parse = copy.deepcopy(parsed_dict)

        #     for condition in substituted_parse["conditions"]:
        #         for i, value in enumerate(condition["value"]):
        #             try:
        #                 if "X" in value:
        #                     if "+" in value:
        #                         new_value = x_val + float(value.split("+")[-1])
        #                     else:
        #                         new_value = x_val
        #                     # print("SUBSTITUTE", condition, value, i, new_value)
        #                     condition["value"][i] = new_value
        #             except TypeError:
        #                 # This is when the target is actually a float
        #                 pass

        #     #print(substituted_parse)
        #     all_concrete_queries.append(substituted_parse)
    else:
        all_concrete_queries.append(parsed_dict)

    # Perfoming the filtering of conditions
    results_ms1_list = []
    results_ms2_list = []

    # Ray Parallel Version
    if ray.is_initialized() and parallel:
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

    print(aggregated_ms1_df)
    
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

    # In order to handle intensities, we will make sure to sort all conditions with 
    # with the conditions that are the reference intensity first, then subsequent conditions
    # that have an intensity match will reference the saved reference intensities
    reference_conditions_register = {} # This will hold all the reference intensity values
    
    # This helps sort the qualifiers
    reference_conditions = []
    nonreference_conditions = []
    for condition in parsed_dict["conditions"]:
        if "qualifiers" in condition:
            if "qualifierintensityreference" in condition["qualifiers"]:
                reference_conditions.append(condition)
                continue
        nonreference_conditions.append(condition)
    all_conditions = reference_conditions + nonreference_conditions

    # These are for the WHERE clause, first lets filter by RT
    for condition in all_conditions:
        if not condition["conditiontype"] == "where":
            continue

        #logging.error("WHERE CONDITION", condition)

        # RT Filters
        if condition["type"] == "rtmincondition":
            rt = condition["value"][0]
            ms2_df = ms2_df[ms2_df["rt"] > rt]
            ms1_df = ms1_df[ms1_df["rt"] > rt]

            continue

        if condition["type"] == "rtmaxcondition":
            rt = condition["value"][0]
            ms2_df = ms2_df[ms2_df["rt"] < rt]
            ms1_df = ms1_df[ms1_df["rt"] < rt]

            continue

    # These are for the WHERE clause
    for condition in all_conditions:
        if not condition["conditiontype"] == "where":
            continue

        #logging.error("WHERE CONDITION", condition)

        # Filtering MS2 Product Ions
        if condition["type"] == "ms2productcondition":
            mz = condition["value"][0]
            mz_tol = _get_mz_tolerance(condition.get("qualifiers", None), mz)
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            min_int, min_intpercent = _get_minintensity(condition.get("qualifiers", None))

            ms2_filtered_df = ms2_df[(ms2_df["mz"] > mz_min) & (ms2_df["mz"] < mz_max) & (ms2_df["i"] > min_int) & (ms2_df["i_norm"] > min_intpercent)]

            # Setting the intensity match register
            _set_intensity_register(ms2_filtered_df, reference_conditions_register, condition)

            # Applying the intensity match
            ms2_filtered_df = _filter_intensitymatch(ms2_filtered_df, reference_conditions_register, condition)

            # Filtering the actual data structures
            filtered_scans = set(ms2_filtered_df["scan"])
            ms2_df = ms2_df[ms2_df["scan"].isin(filtered_scans)]

            # Filtering the MS1 data now
            ms1_scans = set(ms2_df["ms1scan"])
            ms1_df = ms1_df[ms1_df["scan"].isin(ms1_scans)]

            continue

        # Filtering MS2 Precursor m/z
        if condition["type"] == "ms2precursorcondition":
            mz = condition["value"][0]
            mz_tol = 0.1
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol
            ms2_df = ms2_df[(ms2_df["precmz"] > mz_min) & (ms2_df["precmz"] < mz_max)]

            continue

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

            continue

        # finding MS1 peaks
        if condition["type"] == "ms1mzcondition":
            mz = condition["value"][0]
            mz_tol = 0.1
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            min_int, min_intpercent = _get_minintensity(condition.get("qualifiers", None))
            ms1_filtered_df = ms1_df[(ms1_df["mz"] > mz_min) & (ms1_df["mz"] < mz_max) & (ms1_df["i"] > min_int) & (ms1_df["i_norm"] > min_intpercent)]
            
            # Setting the intensity match register
            _set_intensity_register(ms1_filtered_df, reference_conditions_register, condition)

            # Applying the intensity match
            ms1_filtered_df = _filter_intensitymatch(ms1_filtered_df, reference_conditions_register, condition)

            if len(ms1_filtered_df) == 0:
                return pd.DataFrame(), pd.DataFrame()

            # Filtering the actual data structures
            filtered_scans = set(ms1_filtered_df["scan"])
            ms1_df = ms1_df[ms1_df["scan"].isin(filtered_scans)]

            continue

        if condition["type"] == "rtmincondition":
            continue

        if condition["type"] == "rtmaxcondition":
            continue

        raise Exception("CONDITION NOT HANDLED")

    # These are for the FILTER clause
    for condition in all_conditions:
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
            mz_tol = _get_mz_tolerance(condition.get("qualifiers", None), mz)
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            min_int, min_intpercent = _get_minintensity(condition.get("qualifiers", None))

            ms2_df = ms2_df[(ms2_df["mz"] > mz_min) & (ms2_df["mz"] < mz_max) & (ms2_df["i"] > min_int) & (ms2_df["i_norm"] > min_intpercent)]

    if "comment" in parsed_dict:
        ms1_df["comment"] = parsed_dict["comment"]
        ms2_df["comment"] = parsed_dict["comment"]

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
                groupby_columns = ["scan"]
                kept_columns = ["scan", "rt"]

                if "comment" in ms1_df:
                    groupby_columns.append("comment")
                    kept_columns.append("comment")

                result_df = ms1_df.groupby(groupby_columns).first().reset_index()
                result_df = result_df[kept_columns]

                ms1sum_df = ms1_df.groupby(groupby_columns).sum().reset_index()
                result_df["i"] = ms1sum_df["i"]
            if parsed_dict["querytype"]["datatype"] == "datams2data":
                kept_columns = ["scan", "precmz", "ms1scan", "rt"]
                groupby_columns = ["scan"]

                if "comment" in ms2_df:
                    groupby_columns.append("comment")
                    kept_columns.append("comment")

                result_df = ms2_df.groupby(groupby_columns).first().reset_index()
                result_df = result_df[kept_columns]

                ms2sum_df = ms2_df.groupby(groupby_columns).sum().reset_index()
                result_df["i"] = ms2sum_df["i"]

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
