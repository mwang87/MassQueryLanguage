import msql_parser
import msql_engine
import argparse

def main():
    parser = argparse.ArgumentParser(description="MSQL CMD")
    parser.add_argument('filename', help='Input filename')
    parser.add_argument('query', help='Input Query')
    parser.add_argument('--output_file', default=None, help='output')

    args = parser.parse_args()

    results_df = msql_engine.process_query(args.query, args.filename, cache=True, parallel=False)
    if args.output_file:
        results_df.to_csv(args.output_file, index=False)
    print(results_df)

if __name__ == "__main__":
    main()
