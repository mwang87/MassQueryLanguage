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
                dbc.NavItem(dbc.NavLink("GNPS - Template Dashboard - Version 0.1", href="#")),
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
                    dbc.InputGroupAddon("Spectrum USI", addon_type="prepend"),
                    dbc.Input(id='usi1', placeholder="Enter GNPS USI", value=""),
                ],
                className="mb-3",
            ),
            html.Hr(),
            dbc.InputGroup(
                [
                    dbc.InputGroupAddon("Spectrum USI", addon_type="prepend"),
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

app.layout = html.Div(children=[NAVBAR, BODY])

def _get_url_param(param_dict, key, default):
    return param_dict.get(key, [default])[0]

@app.callback([
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


# @app.callback([
#                 Output('plot_link', 'children')
#               ],
#               [
#                   Input('gnps_tall_table_usi', 'value'),
#                   Input('gnps_quant_table_usi', 'value'),
#                   Input('gnps_metadata_table_usi', 'value'), 
#                 Input('feature', 'value'),
#                 Input("metadata_column", "value"),
#                 Input("facet_column", "value"),
#                 Input("animation_column", "value"),
#                 Input("group_selection", "value"),
#                 Input("color_selection", "value"),
#                 Input("theme", "value"),
#                 Input("plot_type", "value"),
#                 Input("image_export_format", "value"),
#                 Input("points_toggle", "value"),
#                 Input("log_axis", "value"),
#                 Input("lat_column", "value"),
#                 Input("long_column", "value"),
#                 Input("map_animation_column", "value"),
#                 Input("map_scope", "value"),
#               ])
# def draw_link(      gnps_tall_table_usi, 
#                     gnps_quant_table_usi, 
#                     gnps_metadata_table_usi, 
#                     feature_id, 
#                     metadata_column, 
#                     facet_column, 
#                     animation_column, 
#                     group_selection, 
#                     color_selection, 
#                     theme, 
#                     plot_type, 
#                     image_export_format, 
#                     points_toggle, 
#                     log_axis,
#                     lat_column,
#                     long_column,
#                     map_animation_column,
#                     map_scope):
#     # Creating Reproducible URL for Plot
#     url_params = {}
#     url_params["gnps_tall_table_usi"] = gnps_tall_table_usi
#     url_params["gnps_quant_table_usi"] = gnps_quant_table_usi
#     url_params["gnps_metadata_table_usi"] = gnps_metadata_table_usi

#     url_params["feature"] = feature_id
#     url_params["metadata"] = metadata_column
#     url_params["facet"] = facet_column
#     url_params["groups"] = ";".join(group_selection)
#     url_params["plot_type"] = plot_type
#     url_params["color"] = color_selection
#     url_params["points_toggle"] = points_toggle
#     url_params["theme"] = theme
#     url_params["animation_column"] = animation_column

#     # Mapping Options
#     url_params["lat_column"] = lat_column
#     url_params["long_column"] = long_column
#     url_params["map_animation_column"] = map_animation_column
#     url_params["map_scope"] = map_scope
    
#     url_provenance = dbc.Button("Link to this Plot", block=True, color="primary", className="mr-1")
#     provenance_link_object = dcc.Link(url_provenance, href="/?" + urllib.parse.urlencode(url_params) , target="_blank")

#     return [provenance_link_object]


@app.callback([
                Output('output', 'children')
              ],
              [
                  Input('usi1', 'value'),
                  Input('usi2', 'value'),
            ])
def draw_output(usi1, usi2):
    return [usi1+usi2]

# API
@server.route("/api")
def api():
    return "Up"    

if __name__ == "__main__":
    app.run_server(debug=True, port=5000, host="0.0.0.0")
