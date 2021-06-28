import msql_parser
import msql_engine
import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="MSQL CMD")
    parser.add_argument('filename', help='Input filename')
    parser.add_argument('query', help='Input Query')
    parser.add_argument('--output_file', default=None, help='output_file')
    parser.add_argument('--parallel_query', default="NO", help='parallel_query')
    
    args = parser.parse_args()

    grammar_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "msql.ebnf")
    results_df = msql_engine.process_query(args.query, 
                                            args.filename, 
                                            path_to_grammar=grammar_path, 
                                            cache=True, 
                                            parallel=(args.parallel_query == "YES"))
    if args.output_file and len(results_df) > 0:
        results_df["filename"] = os.path.basename(args.filename)
        if ".tsv" in args.output_file:
            results_df.to_csv(args.output_file, index=False, sep="\t")
        else:
            results_df.to_csv(args.output_file, index=False)
    print(results_df)

if __name__ == "__main__":
    main()
