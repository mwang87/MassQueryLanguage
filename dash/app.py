# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_bootstrap_components as dbc
import dash_html_components as html
import dash_table
import plotly.express as px
import plotly.graph_objects as go 
import dash_daq as daq
from dash.dependencies import Input, Output, State
import os
from zipfile import ZipFile
import urllib.parse
from flask import Flask, send_from_directory

import pandas as pd
import requests
import uuid
import werkzeug
import glob

import pymzml
import numpy as np
from tqdm import tqdm
import urllib
import json

from collections import defaultdict
import uuid

from flask_caching import Cache
import tasks
import msql_parser

server = Flask(__name__)
app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = 'GNPS - Template'

cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'temp/flask-cache',
    'CACHE_DEFAULT_TIMEOUT': 0,
    'CACHE_THRESHOLD': 10000
})

server = app.server

NAVBAR = dbc.Navbar(
    children=[
        dbc.NavbarBrand(
            html.Img(src="https://gnps-cytoscape.ucsd.edu/static/img/GNPS_logo.png", width="120px"),
            href="https://gnps.ucsd.edu"
        ),
        dbc.Nav(
            [
                dbc.NavItem(dbc.NavLink("GNPS - MSQL Dashboard - Version 0.1", href="#")),
            ],
        navbar=True)
    ],
    color="light",
    dark=False,
    sticky="top",
)

file_list = glob.glob("./test/*.mzML")
file_list = [os.path.basename(filename) for filename in file_list]
file_list = [{"label": filename, "value": filename} for filename in file_list]

DATASELECTION_CARD = [
    dbc.CardHeader(html.H5("Data Selection")),
    dbc.CardBody(
        [   
            html.H5(children='GNPS Data Selection'),
            dbc.InputGroup(
                [
                    dbc.InputGroupAddon("Query", addon_type="prepend"),
                    dbc.Input(id='query', placeholder="Enter Query", value=""),
                ],
                className="mb-3",
            ),
            dbc.InputGroup(
                [
                    dbc.InputGroupAddon("Filename", addon_type="prepend"),
                    dbc.Select(
                        id="filename",
                        options=file_list,
                        value="GNPS00002_A3_p.mzML"
                    )
                ],
                className="mb-3",
            ),
            html.H5(children='Plotting Options'),
            dbc.InputGroup(
                [
                    dbc.InputGroupAddon("x_axis", addon_type="prepend"),
                    dbc.Input(id='x_axis', placeholder="Enter Query", value=""),
                ],
                className="mb-3",
            ),
            dbc.InputGroup(
                [
                    dbc.InputGroupAddon("y_axis", addon_type="prepend"),
                    dbc.Input(id='y_axis', placeholder="Enter Query", value=""),
                ],
                className="mb-3",
            ),
            dbc.InputGroup(
                [
                    dbc.InputGroupAddon("facet_column", addon_type="prepend"),
                    dbc.Input(id='facet_column', placeholder="Enter Facet", value=""),
                ],
                className="mb-3",
            ),
            html.Br(),
            html.Hr(),
            html.H5(children='Query Parse'),
            dcc.Loading(
                id="output_parse",
                children=[html.Div([html.Div(id="loading-output-21")])],
                type="default",
            ),
        ]
    )
]

LEFT_DASHBOARD = [
    html.Div(
        [
            html.Div(DATASELECTION_CARD),
        ]
    )
]

MIDDLE_DASHBOARD = [
    dbc.CardHeader(html.H5("Data Exploration")),
    dbc.CardBody(
        [
            dcc.Loading(
                id="output",
                children=[html.Div([html.Div(id="loading-output-23")])],
                type="default",
            ),
            dcc.Loading(
                id="plotting",
                children=[html.Div([html.Div(id="loading-output-26")])],
                type="default",
            ),
        ]
    )
]

CONTRIBUTORS_DASHBOARD = [
    dbc.CardHeader(html.H5("Contributors")),
    dbc.CardBody(
        [
            "Mingxun Wang PhD - UC San Diego",
            html.Br(),
            html.Br(),
            html.H5("Citation"),
            html.A('Mingxun Wang, Jeremy J. Carver, Vanessa V. Phelan, Laura M. Sanchez, Neha Garg, Yao Peng, Don Duy Nguyen et al. "Sharing and community curation of mass spectrometry data with Global Natural Products Social Molecular Networking." Nature biotechnology 34, no. 8 (2016): 828. PMID: 27504778', 
                    href="https://www.nature.com/articles/nbt.3597")
        ]
    )
]

EXAMPLES_DASHBOARD = [
    dbc.CardHeader(html.H5("Examples")),
    dbc.CardBody(
        [
            html.A('Get all MS2 scans in file', 
                    href="/?query=QUERY scaninfo(MS2DATA)"),
            html.Br(),
            html.A('Get TIC of MS1 in file', 
                    href="/?query=QUERY scansum(MS1DATA)&x_axis=rt&y_axis=i"),
            html.Br(),
            html.A('Get XIC of MS1 in file', 
                    href="/?query=QUERY scansum(MS1DATA) FILTER MS1MZ=100:TOLERANCEMZ=0.1&x_axis=rt&y_axis=i"),
            html.Br(),
            html.A('Get MS2 peaks where a product ion is present', 
                    href="/?query=QUERY MS2DATA WHERE MS2PROD=226.18"),
            html.Br(),
            html.A('Get MS2 info where a product ion is present', 
                    href="/?query=QUERY scaninfo(MS2DATA) WHERE MS2PROD=167.0857:TOLERANCEPPM=5"),
            html.Br(),
            html.A('Get MS2 info where a product ion and neutral loss is present', 
                    href="/?query=QUERY scaninfo(MS2DATA) WHERE MS2NL=176.0321 AND MS2PROD=85.02915"),
            html.Br(),
            html.A('Get MS1 peaks where a MS2 with product ion is present', 
                    href="/?query=QUERY MS1DATA WHERE MS2PROD=226.18"),
            html.Br(),
            html.A('Sub Query', 
                    href="/?query=QUERY scanrangesum(MS1DATA, TOLERANCE=0.1) WHERE MS1MZ=(QUERY scanmz(MS2DATA) WHERE MS2NL=176.0321 AND MS2PROD=85.02915)")
        ]
    )
]

BODY = dbc.Container(
    [
        dcc.Location(id='url', refresh=False),
        dbc.Row([
            dbc.Col(
                dbc.Card(LEFT_DASHBOARD),
                className="w-50"
            ),
            dbc.Col(
                [
                    dbc.Card(MIDDLE_DASHBOARD),
                    html.Br(),
                    dbc.Card(CONTRIBUTORS_DASHBOARD),
                    html.Br(),
                    dbc.Card(EXAMPLES_DASHBOARD)
                ],
                className="w-50"
            ),
        ], style={"marginTop": 30}),
    ],
    fluid=True,
    className="",
)

app.layout = html.Div(children=[NAVBAR, BODY])

def _get_url_param(param_dict, key, default):
    return param_dict.get(key, [default])[0]

@app.callback([
                Output('query', 'value'),
                Output('x_axis', 'value'),
                Output('y_axis', 'value'),
                Output('facet_column', 'value')
              ],
              [
                  Input('url', 'search')
              ])
def determine_task(search):
    try:
        query_dict = urllib.parse.parse_qs(search[1:])
    except:
        query_dict = {}

    query = _get_url_param(query_dict, "query", 'QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEPPM=5')
    x_axis = _get_url_param(query_dict, "x_axis", dash.no_update)
    y_axis = _get_url_param(query_dict, "y_axis", dash.no_update)
    facet_column = _get_url_param(query_dict, "facet_column", dash.no_update)

    return [query, x_axis, y_axis, facet_column]

@app.callback([
                Output('output', 'children'),
                Output('output_parse', 'children'),
              ],
              [
                  Input('query', 'value'),
                  Input('filename', 'value')
            ])
def draw_output(query, filename):
    parse_results = msql_parser.parse_msql(query)

    results_list = tasks.task_executequery.delay(query, filename)
    results_list = results_list.get()

    table = dash_table.DataTable(
        id='table',
        columns=[{"name": i, "id": i} for i in results_list[0].keys()],
        data=results_list,
        page_size=10
    )

    parse_markdown = dcc.Markdown(
        '''
```json
{}
```
'''.format(json.dumps(parse_results, indent=4)))



    return [table, parse_markdown]


@app.callback([
                Output('plotting', 'children'),
              ],
              [
                  Input('query', 'value'),
                  Input('filename', 'value'),
                  Input('x_axis', 'value'),
                  Input('y_axis', 'value'),
                  Input('facet_column', 'value')
            ])
def draw_plot(query, filename, x_axis, y_axis, facet_column):
    parse_results = msql_parser.parse_msql(query)

    results_list = tasks.task_executequery.delay(query, filename)
    results_list = results_list.get()

    results_df = pd.DataFrame(results_list)

    import plotly.express as px

    try:
        fig = px.scatter(results_df, x=x_axis, y=y_axis, facet_row=facet_column)
    except:
        fig = px.scatter(results_df, x=x_axis, y=y_axis)

    return [dcc.Graph(figure=fig)]

# API
@server.route("/api")
def api():
    return "Up"    

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
