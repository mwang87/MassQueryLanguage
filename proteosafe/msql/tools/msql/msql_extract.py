import json
import os
import argparse
import glob
import sys
import pandas as pd

def main():
    parser = argparse.ArgumentParser(description="MSQL Query in Proteosafe")
    parser.add_argument('input_folder', help='Input filename')
    parser.add_argument('results_file', help='Input Query')
    parser.add_argument('extract_results_folder', help='Input Query')

    args = parser.parse_args()

    results_df = pd.read_csv(args.results_file, sep='\t')

    results_list = results_df.to_dict(orient="records")
    for result_obj in results_list:
        print(result_obj)
        



if __name__ == "__main__":
    main()
