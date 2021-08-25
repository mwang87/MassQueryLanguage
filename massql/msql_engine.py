import os
import pandas as pd
import numpy as np
import copy
import logging
from tqdm import tqdm

from py_expression_eval import Parser

from massql import msql_parser
from massql import msql_fileloading
from massql import msql_engine_filters
from massql.msql_engine_filters import _get_mz_tolerance, _get_minintensity

math_parser = Parser()
console = logging.StreamHandler()
console.setLevel(logging.INFO)


def DEBUG_MSG(msg):
    import sys

    print(msg, file=sys.stderr, flush=True)

def init_ray():
    import ray
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True, object_store_memory=8000000000, num_cpus=8)


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


def process_query(input_query, input_filename, path_to_grammar=None, cache=True, parallel=False, ms1_df=None, ms2_df=None):
    """
    Process an actual query

    Args:
        input_query ([type]): [description]
        input_filename ([type]): [description]
        path_to_grammar ([type], optional): [description]. Defaults to None.
        cache (bool, optional): [description]. Defaults to True.
        parallel (bool, optional): [description]. Defaults to False.
        ms1_df ([type], optional): [description]. Defaults to None. Pass in if you have these data in memory
        ms2_df ([type], optional): [description]. Defaults to None. Pass in if you have these data in memory

    Returns:
        query results data frame: [description]
    """

    parsed_dict = msql_parser.parse_msql(input_query, path_to_grammar=path_to_grammar)

    return _evalute_variable_query(parsed_dict, input_filename, cache=cache, parallel=parallel, ms1_df=ms1_df, ms2_df=ms2_df)

def _determine_mz_max(mz, ppm_tol, da_tol):
    da_tol = da_tol if da_tol < 10000 else 0
    ppm_tol = ppm_tol if ppm_tol < 10000 else 0
    # We are going to make the bins half of the actual tolerance
    half_delta = max(mz * ppm_tol / 1000000, da_tol) / 2

    half_delta = half_delta if half_delta > 0 else 0.05

    return mz + half_delta

def _evalute_variable_query(parsed_dict, input_filename, cache=True, parallel=False, ms1_df=None, ms2_df=None):
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

    # Variable Expression Parameters
    variable_properties = {}
    variable_properties["has_variable"] = False
    variable_properties["ppm_tolerance"] = 100000
    variable_properties["da_tolerance"] = 100000
    variable_properties["query_ms1"] = False
    variable_properties["query_ms2"] = False
    variable_properties["query_ms2prec"] = False
    variable_properties["min"] = 0
    variable_properties["max"] = 1000000
    variable_properties["mindefect"] = 0
    variable_properties["maxdefect"] = 1
    

    # Checking for ranges in query
    new_conditions = []
    for condition in parsed_dict["conditions"]:
        if condition["type"] == "xcondition":
            if "min" in condition:
                variable_properties["min"] = condition["min"]
                variable_properties["max"] = condition["max"]
            if "mindefect" in condition:
                variable_properties["mindefect"] = condition["mindefect"]
                variable_properties["maxdefect"] = condition["maxdefect"]
        else:
            new_conditions.append(condition)
    parsed_dict["conditions"] = new_conditions

    # Here we will check if there is a variable in the expression
    for condition in parsed_dict["conditions"]:
        for value in condition["value"]:
            try:
                # Checking if X is in any string
                # TODO: Check multiple conditions, to see if any of them have an X, e.g. (101 OR X-10)
                if "X" in value[0]:
                    if value == "X":
                        # This is the main varaible, not expression containing it
                        if condition["type"] == "ms1mzcondition":
                            variable_properties["query_ms1"] = True
                        if condition["type"] == "ms2productcondition":
                            variable_properties["query_ms2"] = True
                        if condition["type"] == "ms2neutrallosscondition":
                            variable_properties["query_ms2"] = True
                        if condition["type"] == "ms2precursorcondition":
                            variable_properties["query_ms2prec"] = True

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

    # Loading data if not passed in 
    if ms1_df is None:
        ms1_df, ms2_df = msql_fileloading.load_data(input_filename, cache=cache)

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
                    if "X" in value:
                        continue
                except TypeError:
                    # This is when the target is actually a float
                    pass
                non_variable_conditions.append(condition)
        presearch_parse["conditions"] = non_variable_conditions
        ms1_df, ms2_df = _executeconditions_query(presearch_parse, input_filename, cache=cache)
        variable_x_ms1_df = ms1_df

        # TODO: Checking if we can prefilter the X variable, if there are conditions
        for condition in parsed_dict["conditions"]:
            if not condition["conditiontype"] == "where":
                continue

            if not "X" in condition["value"]:
                continue
        
            # Filtering MS1 peaks only to consider contention for X
            if condition["type"] == "ms1mzcondition":
                min_int, min_intpercent, min_tic_percent_intensity = _get_minintensity(condition.get("qualifiers", None))
                variable_x_ms1_df = ms1_df[
                    (ms1_df["i"] > min_int) & 
                    (ms1_df["i_norm"] > min_intpercent) & 
                    (ms1_df["i_tic_norm"] > min_tic_percent_intensity)]

        # Here we will start with the smallest mass and then go up
        masses_considered_df_list = []
        if variable_properties["query_ms1"]:
            masses_considered_df_list.append(variable_x_ms1_df["mz"])
        if variable_properties["query_ms2"]:
            masses_considered_df_list.append(ms2_df["mz"])
        if variable_properties["query_ms2prec"]:
            masses_considered_df_list.append(ms2_df["precmz"])

        masses_considered_df = pd.DataFrame()
        masses_considered_df["mz"] = pd.concat(masses_considered_df_list)
        # NOTE: This might cause bugs, we might consider every mass within every single scan, or at least we could make the tolernace as even smaller than half the max
        masses_considered_df["mz_max"] = masses_considered_df["mz"].apply(lambda x: _determine_mz_max(x, variable_properties["ppm_tolerance"], variable_properties["da_tolerance"]))
        
        masses_considered_df = masses_considered_df.sort_values("mz")
        masses_list = masses_considered_df.to_dict(orient="records")

        running_max_mz = 0
        for masses_obj in tqdm(masses_list):
            if running_max_mz > masses_obj["mz"]:
                continue

            #######################
            # Writing new query
            #######################
            substituted_parse = copy.deepcopy(parsed_dict)
            mz_val = masses_obj["mz"]

            for condition in substituted_parse["conditions"]:
                for i, value in enumerate(condition["value"]):
                    # Rewriting the condition value
                    try:
                        if "X" in value:
                            new_value = math_parser.parse(value).evaluate({
                                "X" : mz_val
                            })
                            condition["value"][i] = new_value
                    except TypeError:
                        # This is when the target is actually a float
                        pass

                    # Rewriting the qualifier values
                    try:
                        if "qualifiers" in condition:
                            for qualifier in condition["qualifiers"]:
                                if "qualifier" in qualifier:
                                    if "value" in condition["qualifiers"][qualifier]:
                                        old_value = condition["qualifiers"][qualifier]["value"]
                                        condition["qualifiers"][qualifier]["value"] = old_value.replace("X", str(mz_val))
                    except AttributeError:
                        pass
            
            # Let's consider this mz
            running_max_mz = masses_obj["mz_max"]

            # Checking the x conditions
            substituted_parse["comment"] = str(mz_val)
            if mz_val < variable_properties["min"] or mz_val > variable_properties["max"]:
                continue
            mz_val_defect = mz_val - int(mz_val)
            if mz_val_defect < variable_properties["mindefect"] or mz_val_defect > variable_properties["maxdefect"]:
                continue

            all_concrete_queries.append(substituted_parse)
    else:
        all_concrete_queries.append(parsed_dict)

    print("TOTAL QUERIES", len(all_concrete_queries))

    # Perfoming all the concrete queries
    collated_list = [] # This list holds the collated set of results from each query, final result is a concat of all of them

    # Ray Parallel Version
    execute_serial = True
    if parallel:
        import ray
        import msql_engine_ray

        if ray.is_initialized():
            # TODO: Divide up the parallel thing
            chunk_size = 100
            concrete_query_lists = [all_concrete_queries[i:i + chunk_size] for i in range(0, len(all_concrete_queries), chunk_size)]
            futures = [msql_engine_ray._executeconditions_query_ray.remote(concrete_query_list, input_filename, ms1_input_df=ms1_df, ms2_input_df=ms2_df, cache=cache) for concrete_query_list in concrete_query_lists]
            all_ray_results = ray.get(futures)

            # Flattening this list of lists
            collated_list = [item for sublist in all_ray_results for item in sublist]

            execute_serial = False
    
    # This is the fallback
    if execute_serial:
        # Serial Version
        for concrete_query in tqdm(all_concrete_queries):
            results_ms1_df, results_ms2_df = _executeconditions_query(concrete_query, input_filename, ms1_input_df=ms1_df, ms2_input_df=ms2_df, cache=cache)
            
            collated_df = _executecollate_query(parsed_dict, results_ms1_df, results_ms2_df)
            collated_list.append(collated_df)

    # Concatenating all the results
    collated_df = pd.concat(collated_list)
    collated_df = collated_df.reset_index(drop=True)

    # Lets try to remove duplicates
    try:
        if "comment" in collated_df:
            collated_df["truncated_comment"] = collated_df["comment"].astype(float).astype(int)
            collated_df = collated_df.drop_duplicates(subset=["scan", "truncated_comment"])
            collated_df = collated_df.drop("truncated_comment", axis=1)
    except:
        pass
        
    return collated_df


def _executeconditions_query(parsed_dict, input_filename, ms1_input_df=None, ms2_input_df=None, cache=True):
    # This function attempts to find the data that the query specifies in the conditions
    
    #import json
    #print("parsed_dict", json.dumps(parsed_dict, indent=4))

    # Let's apply this to real data
    if ms1_input_df is None and ms2_input_df is None:
        ms1_df, ms2_df = msql_fileloading.load_data(input_filename, cache=cache)
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

    # These are for the WHERE clause, first lets filter by RT and polarity and scan
    for condition in all_conditions:
        if not condition["conditiontype"] == "where":
            continue

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
    
        # Polarity Filters
        if condition["type"] == "polaritycondition":
            polaritycondition = condition["value"][0]
            if polaritycondition == "positivepolarity":
                ms2_df = ms2_df[ms2_df["polarity"] == 1]
                ms1_df = ms1_df[ms1_df["polarity"] == 1]
            if polaritycondition == "negativepolarity":
                ms2_df = ms2_df[ms2_df["polarity"] == 2]
                ms1_df = ms1_df[ms1_df["polarity"] == 2]

            continue

        # Scan Filters
        if condition["type"] == "scanmincondition":
            scan = int(condition["value"][0])
            ms2_df = ms2_df[ms2_df["scan"] >= scan]
            ms1_df = ms1_df[ms1_df["scan"] >= scan]

            continue
            
        if condition["type"] == "scanmaxcondition":
            scan = int(condition["value"][0])
            ms2_df = ms2_df[ms2_df["scan"] <= scan]
            ms1_df = ms1_df[ms1_df["scan"] <= scan]

            continue

        # Charge Filters
        if condition["type"] == "chargecondition":
            charge = int(condition["value"][0])
            ms2_df = ms2_df[ms2_df["charge"] == charge]

            # Filtering the MS1 data now
            ms1_scans = set(ms2_df["ms1scan"])
            ms1_df = ms1_df[ms1_df["scan"].isin(ms1_scans)]

    # These are for the WHERE clause for peaks
    for condition in all_conditions:
        if not condition["conditiontype"] == "where":
            continue

        # Filtering MS2 Product Ions
        if condition["type"] == "ms2productcondition":
            ms1_df, ms2_df = msql_engine_filters.ms2prod_condition(condition, ms1_df, ms2_df, reference_conditions_register)
            continue

        # Filtering MS2 Precursor m/z
        if condition["type"] == "ms2precursorcondition":
            ms1_df, ms2_df = msql_engine_filters.ms2prec_condition(condition, ms1_df, ms2_df, reference_conditions_register)
            continue

        # Filtering MS2 Neutral Loss
        if condition["type"] == "ms2neutrallosscondition":
            ms1_df, ms2_df = msql_engine_filters.ms2nl_condition(condition, ms1_df, ms2_df, reference_conditions_register)
            continue

        # finding MS1 peaks
        if condition["type"] == "ms1mzcondition":
            ms1_df, ms2_df = msql_engine_filters.ms1_condition(condition, ms1_df, ms2_df, reference_conditions_register)
            continue

        skip_conditions = [ "rtmincondition", 
                            "rtmaxcondition", 
                            "polaritycondition", 
                            "scanmincondition", 
                            "scanmaxcondition",
                            "chargecondition"]
        
        if condition["type"] in skip_conditions:
            continue

        raise Exception("CONDITION NOT HANDLED")

    # These are for the FILTER clause
    for condition in all_conditions:
        if not condition["conditiontype"] == "filter":
            continue

        logging.error("FILTER CONDITION", condition)

        # filtering MS1 peaks
        if condition["type"] == "ms1mzcondition":
            if len(ms1_df) == 0:
                continue

            mz = condition["value"][0]
            mz_tol = 0.1
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol
            ms1_df = ms1_df[(ms1_df["mz"] > mz_min) & (ms1_df["mz"] < mz_max)]

            continue
        
        if condition["type"] == "ms2productcondition":
            if len(ms2_df) == 0:
                continue

            mz = condition["value"][0]
            mz_tol = _get_mz_tolerance(condition.get("qualifiers", None), mz)
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            min_int, min_intpercent, min_tic_percent_intensity = _get_minintensity(condition.get("qualifiers", None))

            ms2_df = ms2_df[(ms2_df["mz"] > mz_min) & 
                            (ms2_df["mz"] < mz_max) & 
                            (ms2_df["i"] > min_int) & 
                            (ms2_df["i_norm"] > min_intpercent) & 
                            (ms2_df["i_tic_norm"] > min_tic_percent_intensity)]

    if "comment" in parsed_dict:
        ms1_df["comment"] = parsed_dict["comment"]
        ms2_df["comment"] = parsed_dict["comment"]

    return ms1_df, ms2_df

def _executecollate_query(parsed_dict, ms1_df, ms2_df):
    # This function takes the dataframes from executing the conditions and returns the proper formatted version

    # Early Exit
    if len(ms1_df) == 0 and len(ms2_df) == 0:
        return pd.DataFrame()

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
                if len(ms1_df) == 0:
                    return ms1_df

                ms1sum_df = ms1_df.groupby("scan").sum().reset_index()

                ms1_df = ms1_df.groupby("scan").first().reset_index()
                ms1_df["i"] = ms1sum_df["i"]

                return ms1_df
            if parsed_dict["querytype"]["datatype"] == "datams2data":
                if len(ms2_df) == 0:
                    return ms2_df

                ms2sum_df = ms2_df.groupby("scan").sum().reset_index()
                
                ms2_df = ms2_df.groupby("scan").first().reset_index()
                ms2_df["i"] = ms2sum_df["i"]

                return ms2_df

        if parsed_dict["querytype"]["function"] == "functionscanmz":
            if len(ms2_df) == 0:
                return ms2_df

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

        # scaninfo return function
        if parsed_dict["querytype"]["function"] == "functionscaninfo":
            result_df = pd.DataFrame()

            if parsed_dict["querytype"]["datatype"] == "datams1data":
                if len(ms1_df) == 0:
                    return pd.DataFrame()

                groupby_columns = ["scan"]
                kept_columns = ["scan", "rt"]

                if "comment" in ms1_df:
                    groupby_columns.append("comment")
                    kept_columns.append("comment")

                result_df = ms1_df.groupby(groupby_columns).first().reset_index()
                result_df = result_df[kept_columns]
                result_df["mslevel"] = 1

                ms1sum_df = ms1_df.groupby(groupby_columns).sum().reset_index()
                ms1norm_df = ms1_df.groupby(groupby_columns).max().reset_index()
                result_df["i"] = ms1sum_df["i"]
                result_df["i_norm"] = ms1norm_df["i_norm"]
            if parsed_dict["querytype"]["datatype"] == "datams2data":
                if len(ms2_df) == 0:
                    return pd.DataFrame()

                kept_columns = ["scan", "precmz", "ms1scan", "rt", "charge"]
                groupby_columns = ["scan"]

                if "comment" in ms2_df:
                    groupby_columns.append("comment")
                    kept_columns.append("comment")

                result_df = ms2_df.groupby(groupby_columns).first().reset_index()
                result_df = result_df[kept_columns]

                ms2sum_df = ms2_df.groupby(groupby_columns).sum().reset_index()
                ms2norm_df = ms2_df.groupby(groupby_columns).max().reset_index()

                result_df["i"] = ms2sum_df["i"]
                result_df["i_norm"] = ms2norm_df["i_norm"]
                result_df["mslevel"] = 2

                # Calculating the MS1 i_norm and then joining on the ms1scan
                try:
                    ms1norm_df = ms1_df.groupby(groupby_columns).max().reset_index()
                    ms1norm_df["ms1scan"] = ms1norm_df["scan"]
                    ms1norm_df["i_norm_ms1"] = ms1norm_df["i_norm"]
                    ms1norm_df = ms1norm_df[["ms1scan", "i_norm_ms1"]]
                    result_df = result_df.merge(ms1norm_df, how="left", on="ms1scan")
                except:
                    pass

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
