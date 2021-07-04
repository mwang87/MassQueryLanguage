import json
import os
import argparse
import shutil
import glob
import sys
import requests
import pandas as pd
import ming_proteosafe_library
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Staging public data for Nextflow")
    parser.add_argument('params_xml', help='output_staged')
    parser.add_argument('output_staged', help='output_staged')

    args = parser.parse_args()

    params_obj = ming_proteosafe_library.parse_xml_file(open(args.params_xml))
    dataset_subset = []
    try:
        dataset_subset = params_obj["DATASETS"][0].split("\n")
        dataset_subset = [dataset for dataset in dataset_subset if len(dataset) > 3]
    except:
        pass

    # Getting all GNPS Datasets
    all_datasets = requests.get("https://massive.ucsd.edu/ProteoSAFe/datasets_json.jsp").json()["datasets"]
    #gnps_datasets = [dataset for dataset in all_datasets if "GNPS" in dataset["title"].upper()]

    if len(dataset_subset) > 0:
        all_datasets = [dataset for dataset in all_datasets if dataset["dataset"] in dataset_subset]
    
    print("NUMBER DATASETS", len(all_datasets))

    if len(all_datasets) > 20:
        print("Too Many Datasets, please apply subsets")
        exit(1)

    for dataset in all_datasets:
        print("linking", dataset["dataset"])
        link_dataset(dataset["dataset"], args.output_staged)

def link_dataset(accession, output_folder):
    source_ccms_peak = os.path.join("/data/massive-ro/{}/ccms_peak".format(accession))

    all_files = []
    all_files += glob.glob(os.path.join(source_ccms_peak, "**/*mzML"), recursive=True)
    all_files += glob.glob(os.path.join(source_ccms_peak, "**/*mzXML"), recursive=True)

    for filepath in all_files:
        try:
            print(filepath)
            target_location = filepath.replace("/data/massive-ro", output_folder)
            output_path = Path(target_location)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.symlink_to(filepath)
        except:
            pass



if __name__ == "__main__":
    main()
