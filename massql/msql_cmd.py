#!/usr/bin/env python

import argparse
import os
import sys
import json
import uuid
import pandas as pd

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from massql import msql_parser
from massql import msql_engine
from massql import msql_extract

def main():
    parser = argparse.ArgumentParser(description="MSQL CMD")
    parser.add_argument('filename', help='Input filename')
    parser.add_argument('query', help='Input Query')
    parser.add_argument('--output_file', default=None, help='output results filename, if filename is too long will truncate filename')
    parser.add_argument('--parallel_query', default="NO", help='YES to make it parallel with ray locally, NO is default')
    
    parser.add_argument('--cache', default=None, help='feather cache with feather, no caching is the default')
    parser.add_argument('--cache_filename', default=None, help='Path to explicit cache filename, must have cache set to YES')
    parser.add_argument('--cache_dir', default=None, help='Path to cache directory, must have cache set to YES. Mutually exclusive to cache_filename. Additionally, caching filename will automatically be hashed')

    parser.add_argument('--original_path', default=None, help='Original absolute path for the filename, useful in proteosafe')
    parser.add_argument('--extract_mzML', default=None, help='Extracting spectra found as mzML file, if filename is too long will truncate filename')
    parser.add_argument('--extract_json', default=None, help='Extracting spectra found as json file, each spectrum is a line, if filename is too long, wiil truncate',)
    parser.add_argument('--maxfilesize', default=None, help='Maximum file size in MB')
    
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

    # Checking the input file for size
    if args.maxfilesize is not None:
        if os.path.isfile(args.filename):
            if os.path.getsize(args.filename) / 1024 / 1024 > int(args.maxfilesize):
                print("File is too big, exiting")
                exit(0)

    # Executing
    all_results_list = []
    for i, query in enumerate(all_queries):
        results_df = msql_engine.process_query(query, 
                                                args.filename, 
                                                cache=args.cache, 
                                                cache_filename=args.cache_filename,
                                                cache_dir=args.cache_dir)

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

    # Handling output filename
    output_results_filename = args.output_file
    output_file_toolong_unique_prefix = str(uuid.uuid4()).replace("-", "") + "_" 

    if output_results_filename is not None:
        if len(os.path.basename(output_results_filename)) > 80:
            output_results_filename = os.path.join(os.path.split(output_results_filename)[0], 
                                                  output_file_toolong_unique_prefix + os.path.basename(output_results_filename)[-80:])
    
    if output_results_filename and len(results_df) > 0:
        results_df["filename"] = os.path.basename(args.filename)

        # This is for GNPS and GNPS2
        if args.original_path is not None:
            useful_filename = args.original_path
            # TODO: Clean up for ProteoSAFe
            useful_filename = useful_filename.split("demangled_spectra/")[-1]

            # Cleanup for repository search
            useful_filename = useful_filename.replace("/data/ccms-data/uploads/", "")

            if "/data/nf_data/server/nf_tasks/" in useful_filename:
                useful_filename = useful_filename.replace("/data/nf_data/server/nf_tasks/", "")
                # Get the second folder name from path with python PathLib
                import pathlib
                task = pathlib.Path(useful_filename).parts[0]
                useful_filename = useful_filename.replace(task + "/", "")

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

        if ".tsv" in output_results_filename:
            results_df.to_csv(output_results_filename, index=False, sep="\t", columns=columns)
        else:
            results_df.to_csv(output_results_filename, index=False, columns=columns)

        # Extracting
        if args.extract_json is not None and len(results_df) > 0:
            print("Extracting {} spectra".format(len(results_df)))
            try:
                output_json_filename = args.extract_json
                if output_json_filename is not None:
                    if len(os.path.basename(output_json_filename)) > 80:
                        output_json_filename = os.path.join(os.path.split(output_json_filename)[0], 
                                                            output_file_toolong_unique_prefix + os.path.basename(output_json_filename)[-80:])

                msql_extract._extract_spectra(results_df, os.path.dirname(args.filename), output_json_filename=output_json_filename)
            except:
                print("Extraction Failed")
                

if __name__ == "__main__":
    main()
