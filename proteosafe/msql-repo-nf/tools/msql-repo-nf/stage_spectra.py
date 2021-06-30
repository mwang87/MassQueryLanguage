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

    for dataset in gnps_datasets:
        link_dataset(dataset["dataset"], args.output_staged)

def link_dataset(accession, output_folder):
    source_ccms_peak = os.path.join("/data/massive/{}/ccms_peak".format(accession))
    if not os.path.exists(source_ccms_peak):
        return
    
    target_location = os.path.join(output_folder, accession, "ccms_peak")
    output_path = Path(target_location)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.symlink_to(source_ccms_peak)



if __name__ == "__main__":
    main()
