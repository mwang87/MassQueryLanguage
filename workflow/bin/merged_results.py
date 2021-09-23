import argparse
import os
import glob
import json
import uuid
import pandas as pd

def main():
    parser = argparse.ArgumentParser(description="Merge tsv files")
    parser.add_argument('tsv_folder', help='tsv_folder')
    parser.add_argument('--output_tsv', default=None, help='Output Summary Extraction File')
    parser.add_argument('--output_tsv_prefix', default=None, help='Output Summary Extraction output_tsv_prefix')

    args = parser.parse_args()

    all_results_list = []

    all_tsv_files = glob.glob(os.path.join(args.tsv_folder, "*.tsv"))

    for input_filename in all_tsv_files:
        try:
            df = pd.read_csv(input_filename, sep="\t")
            if len(df) > 0:
                all_results_list.append(df)
        except:
            pass

    # Merging all the results
    merged_result_df = pd.concat(all_results_list)
    if args.output_tsv is not None:
        merged_result_df.to_csv(args.output_tsv, sep="\t", index=False)
    elif args.output_tsv_prefix is not None:
        merged_result_df.to_csv(args.output_tsv_prefix + "_" +  str(uuid.uuid4()) + ".tsv", sep="\t", index=False)

if __name__ == "__main__":
    main()
