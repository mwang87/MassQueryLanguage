import json
import os
import argparse
import glob
import sys
import pandas as pd
import pymzml

def main():
    parser = argparse.ArgumentParser(description="MSQL Query in Proteosafe")
    parser.add_argument('input_folder', help='Input filename')
    parser.add_argument('results_file', help='Input Query')
    parser.add_argument('extract_results_folder', help='Input Query')

    args = parser.parse_args()

    results_df = pd.read_csv(glob.glob(args.results_file, "*")[0], sep='\t')

    try:
        _extract_spectra(results_df, args.extract_results_folder, os.path.join(args.input_folder, "extracted.mgf"))
    except:
        print("FAILURE ON EXTRACTION")
        raise
        pass
        
    
def _extract_spectra(results_df, input_spectra_folder, output_filename):
    spectrum_list = []

    results_list = results_df.to_dict(orient="records")
    for result_obj in results_list:
        input_spectra_filename = os.path.join(input_spectra_folder, result_obj["mangled_filename"])
        if ".mzML" in input_spectra_filename:
            MS_precisions = {
                1: 5e-6,
                2: 20e-6,
                3: 20e-6,
                4: 20e-6,
                5: 20e-6,
                6: 20e-6,
                7: 20e-6,
            }
            run = pymzml.run.Reader(input_spectra_filename, MS_precisions=MS_precisions)
            scan_number = result_obj["scan"]

            print(result_obj)
            print(run[scan_number])

            spec = run[str(scan_number)]

            peaks = spec.peaks("raw")

            spectrum_obj = {}
            spectrum_obj["peaks"] = peaks
            spectrum_obj["scan"] = scan_number

            if spec.ms_level > 1:
                msn_mz = spec.selected_precursors[0]["mz"]
                spectrum_obj["precursor_mz"] = msn_mz

            spectrum_list.append(spectrum_obj)

    # Writing the spectrum now
    print(len(spectrum_list))


if __name__ == "__main__":
    main()
