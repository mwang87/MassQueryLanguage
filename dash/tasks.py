from celery import Celery
import glob
import sys
import os

import msql_parser
import msql_engine

from celery.signals import worker_ready

celery_instance = Celery('tasks', backend='redis://msql-redis', broker='pyamqp://guest@msql-rabbitmq//', worker_redirect_stdouts=False)


@celery_instance.task(time_limit=60)
def task_computeheartbeat():
    print("UP", file=sys.stderr, flush=True)
    return "Up"

@celery_instance.task(time_limit=60)
def task_executequery(query, filename):
    
    parse_results = msql_parser.parse_msql(query)
    results_df = msql_engine.process_query(query, filename)

    return results_df.to_dict(orient="records")


celery_instance.conf.task_routes = {
    'tasks.task_computeheartbeat': {'queue': 'worker'},
    'tasks.task_executequery': {'queue': 'worker'},
}