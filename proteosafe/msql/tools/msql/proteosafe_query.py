import msql_parser
import msql_engine
import json
import os
import argparse
import glob
import sys
import pandas as pd

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

    input_files_list = glob.glob(os.path.join(input_folder, "*.mzML"))

    all_results_list = []
    for input_filename in input_files_list:
        print(input_filename)

        results_df = msql_engine.process_query(msql_query, input_filename, path_to_grammar=path_to_grammar, cache=False)
        real_filename = mangled_mapping[os.path.basename(input_filename)]
        results_df["filename"] = real_filename

        all_results_list.append(results_df)

    merged_results_df = pd.concat(all_results_list)

    output_results_file = os.path.join(output_folder, "results.tsv")
    merged_results_df.to_csv(output_results_file, sep='\t', index=False)

if __name__ == "__main__":
    main()
