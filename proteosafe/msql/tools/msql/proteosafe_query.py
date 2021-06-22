import msql_parser
import msql_engine
import json
import os
import argparse
import glob
import sys
import pandas as pd
import ray

import ming_proteosafe_library

def main():
    input_folder = sys.argv[1]
    workflow_params = sys.argv[2]
    output_folder = sys.argv[3]
    path_to_grammar = sys.argv[4]

    # Initialize Ray
    msql_engine.init_ray()

    params_obj = ming_proteosafe_library.parse_xml_file(open(workflow_params))
    mangled_mapping = ming_proteosafe_library.get_mangled_file_mapping(params_obj)
    
    msql_query = params_obj["QUERY"][0]
    PARALLEL = params_obj["PARALLEL"][0]

    input_files_list = glob.glob(os.path.join(input_folder, "*.mzML"))
    input_files_list += glob.glob(os.path.join(input_folder, "*.mgf"))

    all_results_list = []

    # Parallel Version
    if len(input_files_list) > 1:
        all_futures = []

        for input_filename in input_files_list:
            print(input_filename)

            results_future = execute_query_ray.remote(msql_query, input_filename, path_to_grammar=path_to_grammar, cache=False, parallel=(PARALLEL=="YES"))
            all_futures.append((results_future, input_filename))

        for result_future, input_filename in all_futures:
            results_df = ray.get(result_future)
            real_filename = mangled_mapping[os.path.basename(input_filename)]
            results_df["filename"] = real_filename

            all_results_list.append(results_df)
    else:
        # Serial Version
        all_results_list = []
        for input_filename in input_files_list:
            print(input_filename)

            results_df = execute_query(msql_query, input_filename, path_to_grammar=path_to_grammar, cache=False, parallel=(PARALLEL=="YES"))
            real_filename = mangled_mapping[os.path.basename(input_filename)]
            results_df["filename"] = real_filename

            all_results_list.append(results_df)

    merged_results_df = pd.concat(all_results_list)
    if "scan" in merged_results_df:
        merged_results_df["scan"] = merged_results_df["scan"].astype(int)

    # Writing a mass range if possible
    if "comment" in merged_results_df:
        try:
            merged_results_df["mz_lower"] = merged_results_df["comment"].astype(float) - 10
            merged_results_df["mz_upper"] = merged_results_df["comment"].astype(float) + 10
        except:
            pass

    output_results_file = os.path.join(output_folder, "results.tsv")
    merged_results_df.to_csv(output_results_file, sep='\t', index=False)


@ray.remote
def execute_query_ray(msql_query, input_filename, path_to_grammar="msql.ebnl", cache=False, parallel=True):
    try:
        results_df = msql_engine.process_query(msql_query, input_filename, path_to_grammar=path_to_grammar, cache=cache, parallel=parallel)
    except:
        return pd.DataFrame()

    return results_df

def execute_query(msql_query, input_filename, path_to_grammar="msql.ebnl", cache=False, parallel=True):
    try:
        results_df = msql_engine.process_query(msql_query, input_filename, path_to_grammar=path_to_grammar, cache=cache, parallel=parallel)
    except:
        return pd.DataFrame()

    return results_df

if __name__ == "__main__":
    main()
