import json
import os
import argparse
import glob
import sys
import pandas as pd

def main():
    parser = argparse.ArgumentParser(description="Proteosafe Wrapper for Nextflow")
    parser.add_argument('workflow_params', help='workflow_params')
    parser.add_argument('nextflow_script', help='nextflow_script')
    parser.add_argument('nextflow_binary', help='nextflow_binary')
    parser.add_argument('output_folder', help='output_folder')
    parser.add_argument('--parametermapping', action='append', help='mapping of current workflow parameters to new parameters in the format: <old parameter>:<new parameter>')
    parser.add_argument('--newparameters', action='append', help='parameter key: <param name>:<parameter value>')

    args = parser.parse_args()

    cmd = "{} run {}".format(args.nextflow_binary, 
                        args.nextflow_script)
    
    print(cmd)

