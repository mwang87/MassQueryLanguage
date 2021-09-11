#!/usr/bin/env python

import argparse
import os
import sys
import json
import pandas as pd

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from massql import msql_parser
from massql import msql_engine
from massql import msql_extract

def main():
    parser = argparse.ArgumentParser(description="MSQL CMD")
    parser.add_argument('filename', nargs='+', help='Input filename')
    parser.add_argument('--query', default="QUERY scaninfo(MS2DATA)", help='Input Query')
    parser.add_argument('--output_file', default=None, help='output results filename')
    parser.add_argument('--parallel_query', default="NO", help='YES to make it parallel with ray locally, NO is default')
    parser.add_argument('--cache', default="YES", help='YES to cache with feather, YES is the default')
    parser.add_argument('--original_path', default=None, help='Original absolute path for the filename, useful in proteosafe')
    parser.add_argument('--extract_json', default=None, help='Extracting spectra found as json file')
    parser.add_argument('--extract_mzML', default=None, help='Extracting spectra found as mzML file, not implemented yet')
    
    args = parser.parse_args()

    print(args)

    PARALLEL = args.parallel_query == "YES"

    if PARALLEL:
        msql_engine.init_ray()

    # Massaging the query on input, we have a system to enable multiple queries to be entered, where results are merged
    # The delimeter is specified as |||
    all_queries = args.query.split("|||")

    # Let's parse first
    for query in all_queries:
        parsed_query = msql_parser.parse_msql(query)
        print(json.dumps(parsed_query, indent=4))

    # Executing
    all_results_list = []
    for filename in args.filename:
        for i, query in enumerate(all_queries):
            results_df = msql_engine.process_query(query, 
                                                    filename, 
                                                    cache=(args.cache == "YES"), 
                                                    parallel=PARALLEL)
            results_df["filename"] = os.path.basename(filename)

            results_df["query_index"] = i
            all_results_list.append(results_df)

    # Merging
    results_df = pd.concat(all_results_list)

    print("#############################")
    print("MassQL Found {} results".format(len(results_df)))
    print("#############################")

    # Setting mzupper and mzlower
    try:
        if "comment" in results_df:
            results_df["mz_lower"] = results_df["comment"].astype(float) - 10
            results_df["mz_upper"] = results_df["comment"].astype(float) + 10
    except:
        pass
    
    if args.output_file and len(results_df) > 0:

        if args.original_path is not None:
            useful_filename = args.original_path
            # TODO: Clean up for ProteoSAFe
            useful_filename = useful_filename.split("demangled_spectra/")[-1]

            # Cleanup for repository search
            useful_filename = useful_filename.replace("/data/ccms-data/uploads/", "")
            
            # Saving output
            results_df["original_path"] = useful_filename

        # Forcing Types
        try:
            results_df["scan"] = results_df["scan"].astype(int)
        except:
            pass

        try:
            results_df["ms1scan"] = results_df["ms1scan"].astype(int)
        except:
            pass

        try:
            results_df["charge"] = results_df["charge"].astype(int)
        except:
            pass
            
        try:
            results_df["mslevel"] = results_df["mslevel"].astype(int)
        except:
            pass

        # Forcing the column order
        columns = list(results_df.columns)
        columns.sort()

        if ".tsv" in args.output_file:
            results_df.to_csv(args.output_file, index=False, sep="\t", columns=columns)
        else:
            results_df.to_csv(args.output_file, index=False, columns=columns)

    # Extracting
    if args.extract_json is not None and len(results_df) > 0:
        print("Extracting {} spectra".format(len(results_df)))
        try:
            msql_extract._extract_spectra(results_df, os.path.dirname(args.filename[0]), output_json_filename=args.extract_json)
        except:
            print("Extraction Failed")
                

if __name__ == "__main__":
    main()
