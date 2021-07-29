import argparse
import pandas as pd
import plotly.express as px

def main():
    parser = argparse.ArgumentParser(description="MSQL CMD")
    parser.add_argument('input_results', help='input_results')
    parser.add_argument('output_summary_html', help='output_summary_html')

    args = parser.parse_args()

    results_df = pd.read_csv(args.input_results, sep='\t')

    print(results_df)
    with open(args.output_summary_html, 'a') as f:
        # Histogram of precursor m/z
        try:
            fig = px.histogram(results_df, 
                                x="precmz",
                                title='Precursor m/z histogram')
            f.write(fig.to_html(full_html=False, include_plotlyjs='cdn'))
        except:
            pass

        
        #f.write(fig2.to_html(full_html=False, include_plotlyjs='cdn'))
        #f.write(fig3.to_html(full_html=False, include_plotlyjs='cdn'))

    


if __name__ == "__main__":
    main()
