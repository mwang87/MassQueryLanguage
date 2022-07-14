# -*- coding: utf-8 -*-
import dash
from dash import dcc
from dash import html
from dash import dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go 

import os
import urllib.parse
from flask import Flask, send_from_directory

import pandas as pd
import requests
import uuid
import werkzeug

import numpy as np
from tqdm import tqdm
import urllib
import json

from collections import defaultdict
import uuid

from flask_caching import Cache

import views
from app import app
dash_app = dash.Dash(
    name="massqlcompendium",
    server=app,
    url_base_pathname="/compendium/",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)

dash_app.title = "MassQL Compendium"

cache = Cache(app, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'temp/flask-cache',
    'CACHE_DEFAULT_TIMEOUT': 0,
    'CACHE_THRESHOLD': 10000
})

NAVBAR = dbc.Navbar(
    children=[
        dbc.NavbarBrand(
            html.Img(src="assets/massql_logo_cropped.png", width="120px"),
            href="https://mwang87.github.io/MassQueryLanguage_Documentation/"
        ),
        dbc.Nav(
            [
                dbc.NavItem(dbc.NavLink("MassQL Sandbox Dashboard - Version 0.3", href="/", external_link=True)),
                dbc.NavItem(dbc.NavLink("MassQL Compendium", href="/compendium/", external_link=True)),
                dbc.NavItem(dbc.NavLink("Documentation", href="https://mwang87.github.io/MassQueryLanguage_Documentation/")),
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
                    dbc.InputGroupText("Spectrum USI"),
                    dbc.Input(id='usi1', placeholder="Enter GNPS USI", value=""),
                ],
                className="mb-3",
            ),
            html.Hr(),
            dbc.InputGroup(
                [
                    dbc.InputGroupText("Spectrum USI"),
                    dbc.Input(id='usi2', placeholder="Enter GNPS USI", value=""),
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
            html.A('Basic', 
                    href=""),
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

dash_app.layout = html.Div(children=[NAVBAR, BODY])

def _get_url_param(param_dict, key, default):
    return param_dict.get(key, [default])[0]

@dash_app.callback([
                Output('usi1', 'value'), 
                Output('usi2', 'value'), 
              ],
              [Input('url', 'search')])
def determine_task(search):
    
    try:
        query_dict = urllib.parse.parse_qs(search[1:])
    except:
        query_dict = {}

    usi1 = _get_url_param(query_dict, "usi1", 'mzspec:MSV000082796:KP_108_Positive:scan:1974')
    usi2 = _get_url_param(query_dict, "usi2", 'mzspec:MSV000082796:KP_108_Positive:scan:1977')

    return [usi1, usi2]



@dash_app.callback([
                Output('output', 'children')
              ],
              [
                  Input('usi1', 'value'),
                  Input('usi2', 'value'),
            ])
def draw_output(usi1, usi2):
    return [usi1+usi2]


if __name__ == "__main__":
    dash_app.run_server(host="0.0.0.0", port=5000, debug=True)