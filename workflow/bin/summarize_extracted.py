import argparse
import json
import pandas as pd
import plotly.express as px

def main():
    parser = argparse.ArgumentParser(description="MSQL CMD")
    parser.add_argument('input_extracted_json', help='input_extracted_json')
    parser.add_argument('output_summary_html', help='output_summary_html')

    args = parser.parse_args()

    input_spectra = json.loads(open(args.input_extracted_json).read())

    peak_list = []
    for spectrum in input_spectra:
        for peak in spectrum['peaks']:
            peak_dict = {}
            peak_dict["mz"] = peak[0]
            if "precmz" in spectrum:
                peak_dict["precmz"] = spectrum["precmz"]

            peak_list.append(peak_dict)

    peaks_df = pd.DataFrame(peak_list)

    with open(args.output_summary_html, 'a') as f:
        # Histogram of precursor m/z
        peakbins = int(max(peaks_df["mz"]) - min(peaks_df["mz"]))
        try:
            fig = px.histogram(peaks_df, 
                                x="mz",
                                title='m/z peak histogram',
                                nbins=peakbins)
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        except:
            pass

        # 2D histogram
        try:
            precbins = int(max(peaks_df["precmz"]) - min(peaks_df["precmz"]))
            fig = px.density_heatmap(peaks_df, 
                                    title='2D m/z peak histogram',
                                    x="mz", 
                                    y="precmz",
                                    color_continuous_scale="Turbo",
                                    nbinsx=peakbins, nbinsy=precbins)
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        except:
            pass

if __name__ == "__main__":
    main()
