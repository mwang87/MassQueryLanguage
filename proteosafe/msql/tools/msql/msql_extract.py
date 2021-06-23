import json
import os
import argparse
import glob
import sys
import pandas as pd
import numpy as np
import pymzml

def main():
    parser = argparse.ArgumentParser(description="MSQL Query in Proteosafe")
    parser.add_argument('input_folder', help='Input filename')
    parser.add_argument('results_file', help='Input Query')
    parser.add_argument('extract_results_folder', help='Input Query')

    args = parser.parse_args()

    results_df = pd.read_csv(glob.glob(os.path.join(args.results_file, "*"))[0], sep='\t')

    try:
        _extract_spectra(results_df, 
                        args.input_folder, 
                        os.path.join(args.extract_results_folder, "extracted.mgf"),
                        os.path.join(args.extract_results_folder, "extracted.tsv"))
    except:
        print("FAILURE ON EXTRACTION")
        pass
        
    
def _extract_spectra(results_df, input_spectra_folder, output_spectra, output_summary=None):
    spectrum_list = []

    # TODO: reduce duplicate scans to extract

    current_scan = 1
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

            try:
                for spec in run:
                    if str(spec.ID) == str(scan_number):
                        break
            except:
                raise

            peaks = spec.peaks("raw")

            # Filtering out zero rows
            peaks = peaks[~np.any(peaks < 1.0, axis=1)]

            # Sorting by intensity
            peaks = peaks[peaks[:, 1].argsort()]

            # Getting top 1000
            #peaks = peaks[-1000:]

            if len(peaks) == 0:
                continue

            mz, intensity = zip(*peaks)

            mz_list = list(mz)
            i_list = list(intensity)

            peaks_list = []
            for i in range(len(mz_list)):
                peaks_list.append([mz_list[i], i_list[i]])

            spectrum_obj = {}
            spectrum_obj["peaks"] = peaks_list
            spectrum_obj["scan"] = scan_number
            spectrum_obj["new_scan"] = current_scan

            result_obj["new_scan"] = current_scan

            if spec.ms_level > 1:
                msn_mz = spec.selected_precursors[0]["mz"]
                spectrum_obj["precursor_mz"] = msn_mz

            spectrum_list.append(spectrum_obj)
            current_scan += 1

    # Writing the updated extraction
    if output_summary is not None:
        df = pd.DataFrame(results_list)
        df.to_csv(output_summary, sep='\t', index=False)

    # Writing the spectrum now
    with open(output_spectra, "w") as o:
        for i, spectrum in enumerate(spectrum_list):
            o.write("BEGIN IONS\n")
            if "precursor_mz" in spectrum:
                o.write("PEPMASS={}\n".format(spectrum["precursor_mz"]))
            o.write("SCANS={}\n".format(spectrum["new_scan"]))
            for peak in spectrum["peaks"]:
                o.write("{} {}\n".format(peak[0], peak[1]))
            o.write("END IONS\n")

if __name__ == "__main__":
    main()
