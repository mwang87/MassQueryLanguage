import msql_parser
import msql_engine
import msql_extract

import argparse
import os
import json
import pandas as pd

def main():
    parser = argparse.ArgumentParser(description="MSQL CMD")
    parser.add_argument('filename', help='Input filename')
    parser.add_argument('query', help='Input Query')
    parser.add_argument('--output_file', default=None, help='output_file')
    parser.add_argument('--parallel_query', default="NO", help='YES to make it parallel with ray locally')
    parser.add_argument('--cache', default="YES", help='YES to cache with feather')
    parser.add_argument('--original_path', default=None, help='Original absolute path, useful in proteosafe')
    parser.add_argument('--extract_mzML', default=None, help='Extracting spectra found as mzML file')
    parser.add_argument('--extract_json', default=None, help='Extracting spectra found as json file')
    
    args = parser.parse_args()

    print(args)

    PARALLEL = args.parallel_query == "YES"

    if PARALLEL:
        msql_engine.init_ray()

    grammar_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "msql.ebnf")

    # Massaging the query on input, we have a system to enable multiple queries to be entered, where results are merged
    # The delimeter is specified as |||
    all_queries = args.query.split("|||")

    # Let's parse first
    for query in all_queries:
        parsed_query = msql_parser.parse_msql(query, grammar_path)
        print(json.dumps(parsed_query, indent=4))

    # Executing
    all_results_list = []
    for i, query in enumerate(all_queries):
        results_df = msql_engine.process_query(query, 
                                                args.filename, 
                                                path_to_grammar=grammar_path, 
                                                cache=(args.cache == "YES"), 
                                                parallel=PARALLEL)

        results_df["query_index"] = i
        all_results_list.append(results_df)

    # Merging
    results_df = pd.concat(all_results_list)

    # Setting mzupper and mzlower
    try:
        if "comment" in results_df:
            results_df["mz_lower"] = results_df["comment"].astype(float) - 10
            results_df["mz_upper"] = results_df["comment"].astype(float) + 10
    except:
        pass
    
    if args.output_file and len(results_df) > 0:
        results_df["filename"] = os.path.basename(args.filename)

        if args.original_path is not None:
            useful_filename = args.original_path
            # TODO: Clean up for ProteoSAFe
            useful_filename = useful_filename.split("demangled_spectra/")[-1]

            # Cleanup for repository search
            useful_filename = useful_filename.replace("/data/ccms-data/uploads/", "")
            

            results_df["original_path"] = useful_filename

            

        if ".tsv" in args.output_file:
            results_df.to_csv(args.output_file, index=False, sep="\t")
        else:
            results_df.to_csv(args.output_file, index=False)

        # Extracting
        if args.extract_json is not None:
            msql_extract._extract_spectra(results_df, os.path.dirname(args.filename), output_json_filename=args.extract_json)

    print("ZZZ", results_df)

if __name__ == "__main__":
    main()
