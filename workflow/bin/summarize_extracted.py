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
        sum_intensity = sum([peak[1] for peak in spectrum['peaks']])
        for peak in spectrum['peaks']:
            peak_dict = {}
            peak_dict["mz"] = peak[0]
            peak_dict["i"] = peak[1]
            peak_dict["i_norm"] = peak[1] / sum_intensity
            
            if "precmz" in spectrum:
                peak_dict["precmz"] = spectrum["precmz"]
            if "comment" in spectrum:
                peak_dict["comment"] = float(spectrum["comment"])

            peak_list.append(peak_dict)

    peaks_df = pd.DataFrame(peak_list)

    with open(args.output_summary_html, 'w') as f:
        # Histogram of precursor m/z
        try:
            peakbins = int(max(peaks_df["mz"]) - min(peaks_df["mz"]))
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

        # 2D histogram with MS2 comment
        try:
            precbins = int(max(peaks_df["precmz"]) - min(peaks_df["precmz"]))
            
            peaks_df["mzminuscomment"] = peaks_df["mz"] - peaks_df["comment"]
            fig = px.density_heatmap(peaks_df, 
                                    title='2D m/z peak histogram minus X',
                                    x="mzminuscomment", 
                                    y="precmz",
                                    color_continuous_scale="Turbo",
                                    nbinsx=peakbins, nbinsy=precbins,
                                    marginal_x="histogram", marginal_y="histogram")
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        except:
            pass

        # 2D histogram with MS1 peaks comment
        try:
            mz_bins = int(max(peaks_df["mz"]) - min(peaks_df["mz"]))
            comment_bins = int(max(peaks_df["comment"]) - min(peaks_df["comment"]))

            peaks_df["mzminuscomment"] = peaks_df["mz"] - peaks_df["comment"]
            fig = px.density_heatmap(peaks_df, 
                                    title='2D m/z peak histogram minus X with margins',
                                    x="mzminuscomment", 
                                    y="comment",
                                    #color_continuous_scale="turbo",
                                    nbinsx=mz_bins, nbinsy=comment_bins,
                                    marginal_x="histogram", marginal_y="histogram")
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))

            fig = px.density_heatmap(peaks_df, 
                                    title='2D m/z peak histogram minus X',
                                    x="mzminuscomment", 
                                    y="comment",
                                    color_continuous_scale="jet",
                                    nbinsx=mz_bins, nbinsy=comment_bins,)
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))

            fig = px.histogram(peaks_df, 
                                x="mzminuscomment",
                                y="i",
                                title='m/z peak sum spectrum minus X histogram',
                                nbins=mz_bins*5)
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))

            fig = px.histogram(peaks_df, 
                                x="mzminuscomment",
                                y="i_norm",
                                title='m/z peak average spectrum minus X histogram',
                                nbins=mz_bins*5)
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        except:
            pass

if __name__ == "__main__":
    main()
