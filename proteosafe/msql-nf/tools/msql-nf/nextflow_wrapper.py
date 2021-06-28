import json
import os
import argparse
import glob
import sys
import pandas as pd
import ming_proteosafe_library

def main():
    parser = argparse.ArgumentParser(description="Proteosafe Wrapper for Nextflow")
    parser.add_argument('workflow_params', help='workflow_params, from proteosafe')
    parser.add_argument('nextflow_script', help='nextflow_script to actually run')
    parser.add_argument('conda_activate', help='conda_activate, this is the path to the activate command in the main conda installation')
    parser.add_argument('nextflow_conda_environment', help='nextflow_conda_environment, this likely should be wherever all your dependencies and nextflow are installed, e.g. nextflow or msql2')
    parser.add_argument('--parametermapping', action='append', help='mapping of current workflow parameters to new parameters in the format: <old parameter>:<new parameter>')
    parser.add_argument('--newparameters', action='append', help='parameter key: <param name>:<parameter value>')

    args = parser.parse_args()

    cmd = "source {} {} && nextflow run {}".format(args.conda_activate, args.nextflow_conda_environment,
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

    #if args.conda is not None:
    #    cmd += " -with-conda {}".format(args.conda)

    print(cmd)
    os.system(cmd)


if __name__ == "__main__":
    main()
