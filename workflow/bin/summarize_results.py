import argparse
import pandas as pd
import plotly.express as px

def main():
    parser = argparse.ArgumentParser(description="Create Figures for results")
    parser.add_argument('input_results', help='input_results')
    parser.add_argument('output_summary_html', help='output_summary_html')

    args = parser.parse_args()

    results_df = pd.read_csv(args.input_results, sep='\t')

    print(results_df)
    with open(args.output_summary_html, 'a') as f:
        # Histogram of precursor m/z
        try:
            bins = int(max(results_df["precmz"]) - min(results_df["precmz"]))
            fig = px.histogram(results_df, 
                                x="precmz",
                                title='Precursor m/z histogram',
                                nbins=bins)
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        except:
            pass

        try:
            bins = int(max(results_df["comment"]) - min(results_df["comment"]))
            fig = px.histogram(results_df, 
                                x="comment",
                                title='Variable Found m/z histogram',
                                nbins=bins)
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        except:
            pass

if __name__ == "__main__":
    main()
