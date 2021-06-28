import json
import os
import argparse
import glob
import sys
import pandas as pd
import ming_proteosafe_library

def main():
    parser = argparse.ArgumentParser(description="Proteosafe Wrapper for Nextflow")
    parser.add_argument('workflow_params', help='workflow_params')
    parser.add_argument('nextflow_script', help='nextflow_script')
    parser.add_argument('nextflow_binary', help='nextflow_binary')
    parser.add_argument('output_folder', help='output_folder')
    parser.add_argument('--conda', default=None, help='conda path')
    parser.add_argument('--parametermapping', action='append', help='mapping of current workflow parameters to new parameters in the format: <old parameter>:<new parameter>')
    parser.add_argument('--newparameters', action='append', help='parameter key: <param name>:<parameter value>')

    args = parser.parse_args()

    cmd = "{} run {}".format(args.nextflow_binary, 
                        args.nextflow_script)
    for parameter in args.newparameters:
        print(parameter)
        cmd += ' --{} "{}"'.format(parameter.split(":")[0], parameter.split(":")[1])

    params_obj = ming_proteosafe_library.parse_xml_file(open(args.workflow_params))
    for parameter in args.parametermapping:
        print(parameter)
        new_param = parameter.split(":")[1]
        old_param = parameter.split(":")[0]
        cmd += ' --{} "{}"'.format(new_param, params_obj[old_param][0])

    if args.conda is not None:
        cmd += " -with-conda {}".format(args.conda)

    os.system(cmd)

