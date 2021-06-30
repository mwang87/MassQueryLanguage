from celery import Celery
import glob
import sys
import os
import requests
import requests_cache
requests_cache.install_cache('/app/test/demo_cache')

import msql_parser
import msql_engine

from celery.signals import worker_ready

celery_instance = Celery('tasks', backend='redis://msql-redis', broker='pyamqp://guest@msql-rabbitmq//', worker_redirect_stdouts=False)


@celery_instance.task(time_limit=60)
def task_computeheartbeat():
    print("UP", file=sys.stderr, flush=True)
    return "Up"

@celery_instance.task(time_limit=120)
def task_executequery(query, filename):
    
    parse_results = msql_parser.parse_msql(query)
    results_df = msql_engine.process_query(query, filename)

    all_results = results_df.to_dict(orient="records")

    try:
        all_results = _enrich_results(all_results)
            
    except:
        pass

    return all_results


def _get_gnps_spectruminfo(spectrumid):
    url = "https://gnps-external.ucsd.edu/gnpsspectrum?SpectrumID={}".format(spectrumid)
    spectruminfo = requests.get(url).json()

    return spectruminfo

def _enrich_results(results_list):
    if len(results_list) > 0:
        for result_obj in results_list[:500]:
            spectrumid = result_obj["scan"]

            if "CCMSLIB" in spectrumid:
                spectruminfo = _get_gnps_spectruminfo(spectrumid)
                result_obj["Compound_Name"] = spectruminfo["annotations"][0]["Compound_Name"][:30]
                result_obj["Adduct"] = spectruminfo["annotations"][0]["Adduct"]
                result_obj["library_membership"] = spectruminfo["spectruminfo"]["library_membership"]
            
    return results_list



celery_instance.conf.task_routes = {
    'tasks.task_computeheartbeat': {'queue': 'worker'},
    'tasks.task_executequery': {'queue': 'worker'},
}