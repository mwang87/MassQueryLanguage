import argparse
import os
import glob
import json
import uuid
import msql_extract

def main():
    parser = argparse.ArgumentParser(description="MSQL CMD")
    parser.add_argument('json_folder', help='json_folder')
    parser.add_argument('output_mzML', help='Output mzML File')
    parser.add_argument('output_mgf', help='Output mgf File')
    parser.add_argument('output_tsv', help='Output tsv File')

    args = parser.parse_args()

    all_json_files = glob.glob(os.path.join(args.json_folder, "*.json"))

    print(all_json_files)

    all_spectra = []

    for json_filename in all_json_files:
        all_spectra += json.loads(open(json_filename).read())

    msql_extract._export_mzML(all_spectra, args.output_mzML)
    msql_extract._export_mgf(all_spectra, args.output_mgf)

    # Formatting output
    print(all_spectra[0].keys())



if __name__ == "__main__":
    main()
