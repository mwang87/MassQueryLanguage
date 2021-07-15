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

    # These settings are for the cluster run
    parser.add_argument('--runcluster', default='NO', help='Tries to run this on the cluster, values are NO and YES')
    parser.add_argument('--clusterconfig', default=None, help='Path to configuration file')
    parser.add_argument('--user', default=None, help='username running the task')
    parser.add_argument('--clusterpythonruntime', default=None, help='cluster python runtime')
    parser.add_argument('--clusterworkprefix', default=None, help='clusterworkprefix')
    parser.add_argument('--task', default=None, help='cluster python runtime')

    args = parser.parse_args()

    # Listing our system
    os.system("hostname")
    os.system("whoami")
    os.system("pwd")
    os.system("ls -l -h")

    if args.runcluster == "YES" and args.user in ["mwang87"]:
        pbs_cluster_work_dir = os.path.join(args.clusterworkprefix, args.task, "work")

        cmd = "source {} {} && nextflow run {} -c {} \
                -work-dir {} \
                --PYTHONRUNTIME={} \
                -with-trace \
                -with-dag \
                -with-report \
                report.html".format(args.conda_activate, args.nextflow_conda_environment,
                            args.nextflow_script, args.clusterconfig, pbs_cluster_work_dir, args.clusterpythonruntime)
    else:
        cmd = "source {} {} && nextflow run {} \
                -with-trace \
                -with-dag \
                -with-report \
                report.html".format(args.conda_activate, args.nextflow_conda_environment,
                            args.nextflow_script)
    for parameter in args.newparameters:
        print(parameter)
        cmd += ' --{} "{}"'.format(parameter.split(":")[0], parameter.split(":")[1].replace("\n", ""))

    params_obj = ming_proteosafe_library.parse_xml_file(open(args.workflow_params))
    for parameter in args.parametermapping:
        print(parameter)
        new_param = parameter.split(":")[1]
        old_param = parameter.split(":")[0]

        cmd += ' --{} "{}"'.format(new_param, params_obj[old_param][0].replace("\n", ""))

    #if args.conda is not None:
    #    cmd += " -with-conda {}".format(args.conda)

    print(cmd)
    return_val = os.system(cmd)
    if return_val != 0:
        raise Exception("Error")


if __name__ == "__main__":
    main()
