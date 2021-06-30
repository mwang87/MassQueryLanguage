import json
import os
import argparse
import shutil
import glob
import sys
import requests
import pandas as pd
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Staging public data for Nextflow")
    parser.add_argument('output_staged', help='output_staged')

    args = parser.parse_args()

    # Getting all GNPS Datasets
    all_datasets = requests.get("https://massive.ucsd.edu/ProteoSAFe/datasets_json.jsp").json()["datasets"]
    gnps_datasets = [dataset for dataset in all_datasets if "GNPS" in dataset["title"].upper()]
    
    print("NUMBER GNPS DATASETS", len(gnps_datasets))

    for dataset in gnps_datasets[:2]:
        print("linking", dataset["dataset"])
        link_dataset(dataset["dataset"], args.output_staged)

def link_dataset(accession, output_folder):
    source_ccms_peak = os.path.join("/data/massive-ro/{}/ccms_peak".format(accession))

    all_files = []
    all_files += glob.glob(os.path.join(source_ccms_peak, "**/*mzML"), recursive=True)
    all_files += glob.glob(os.path.join(source_ccms_peak, "**/*mzXML"), recursive=True)

    for filepath in all_files:
        target_location = filepath.replace("/data/massive-ro/", output_folder)
        output_path = Path(target_location)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.symlink_to(filepath)



if __name__ == "__main__":
    main()
