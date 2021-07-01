import os
import argparse
import requests
from pathlib import Path
import pandas as pd

def main():
    parser = argparse.ArgumentParser(description="Staging public data for Nextflow")
    parser.add_argument('files_list', help='files_list')
    parser.add_argument('output_staged', help='output_staged')

    args = parser.parse_args()

    datasets_df = pd.read_csv(args.files_list)
    datasets_set = set(datasets_df["dataset"])

    # Getting all GNPS Datasets
    all_datasets = requests.get("https://massive.ucsd.edu/ProteoSAFe/datasets_json.jsp").json()["datasets"]
    gnps_datasets = [dataset for dataset in all_datasets if "GNPS" in dataset["title"].upper()]
    gnps_datasets = [dataset for dataset in all_datasets if dataset["dataset"] in datasets_set]

    print("NUMBER GNPS DATASETS", len(gnps_datasets))

    for dataset in gnps_datasets:
        print("linking", dataset["dataset"])
        link_dataset(dataset["dataset"], args.output_staged)

def link_dataset(accession, output_folder):
    source_ccms_peak = os.path.join("/data/massive-ro/{}/ccms_peak".format(accession))

    if os.path.exists(source_ccms_peak):
        target_location = os.path.join(output_folder, accession, "ccms_peak")

        output_path = Path(target_location)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.symlink_to(source_ccms_peak)



if __name__ == "__main__":
    main()