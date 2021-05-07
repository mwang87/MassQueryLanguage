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

import pymzml
import numpy as np
from tqdm import tqdm
import urllib
import json

from collections import defaultdict
import uuid

from flask_caching import Cache


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
                        options=[
                            {"label": "GNPS00002_A3_p.mzML", "value": "GNPS00002_A3_p.mzML"},
                            {"label": "bld_plt1_07_120_1.mzML", "value": "bld_plt1_07_120_1.mzML"},
                            {"label": "QC_0.mzML", "value": "QC_0.mzML"}
                        ],
                        value="GNPS00002_A3_p.mzML"
                    )
                ],
                className="mb-3",
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
            html.A('Get XIC of MS1 in file', 
                    href="/?query=QUERY scansum(MS1DATA) WHERE MS1MZ=100:TOLERANCEMZ=0.1"),
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

    return [query]

@app.callback([
                Output('output', 'children')
              ],
              [
                  Input('query', 'value'),
                  Input('filename', 'value')
            ])
def draw_output(query, filename):
    import msql_parser
    import msql_engine

    results_df = msql_engine.process_query(query, os.path.join("test", filename))

    table = dash_table.DataTable(
        id='table',
        columns=[{"name": i, "id": i} for i in results_df.columns],
        data=results_df.to_dict('records'),
        page_size=20
    )

    return [table]

# API
@server.route("/api")
def api():
    return "Up"    

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
