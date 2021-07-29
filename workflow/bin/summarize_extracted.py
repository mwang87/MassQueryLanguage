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

            peak_list.append(peak_dict)

    peaks_df = pd.DataFrame(peak_list)

    with open(args.output_summary_html, 'a') as f:
        # Histogram of precursor m/z
        try:
            fig = px.histogram(peaks_df, 
                                x="mz",
                                title='m/z peak histogram')
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        except:
            pass

if __name__ == "__main__":
    main()
