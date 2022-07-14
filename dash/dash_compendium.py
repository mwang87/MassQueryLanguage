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


MIDDLE_DASHBOARD = [
    dbc.CardHeader(html.H5("Compendium Exploration")),
    dbc.CardBody(
        [
            dcc.Loading(
                id="compendium_output",
                children=[html.Div([html.Div(id="loading-output-23")])],
                type="default",
            ),
            html.Br(),
            html.Br(),
            html.H4("MassQL Visualization"),
            dcc.Loading(
                id="massql_visualization",
                children=[html.Div([html.Div(id="loading-output-24")])],
                type="default",
            ),
            
        ]
    )
]

CONTRIBUTORS_DASHBOARD = [
    dbc.CardHeader(html.H5("Contributors")),
    dbc.CardBody(
        [
            "Mingxun Wang PhD - UC Riverside",
            html.Br(),
            html.Br(),
            html.H5("Citation"),
            html.Div("Coming Soon!"),
            html.Br(),
            html.Div(["Reach out to colloborate on this project and my lab at UC Riverside!", html.Br(), html.A("Wang Bioinformatics Lab", href="https://www.cs.ucr.edu/~mingxunw/")]),
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
                [
                    dbc.Card(MIDDLE_DASHBOARD),
                    html.Br(),
                    dbc.Card(CONTRIBUTORS_DASHBOARD),
                    html.Br(),
                    dbc.Card(EXAMPLES_DASHBOARD)
                ],
                #className="w-50"
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
                Output('compendium_output', 'children')
              ],
              [
                  Input('url', 'search'),
            ])
def draw_output(url):
    # Here we will draw the compendium table
    compendium_df = pd.read_excel("assets/compendium.xlsx")
    compendium_df = compendium_df[["Query Description", "MassQL Query", "Your name"]]
    compendium_df["Authors"] = compendium_df["Your name"]
    compendium_df = compendium_df[["Query Description", "MassQL Query", "Authors"]]
    results_list = compendium_df.to_dict(orient="records")

    table_obj = dash_table.DataTable(compendium_df.to_dict('records'),[{"name": i, "id": i} for i in compendium_df.columns], 
                    sort_action="native",
                    filter_action="native",
                    row_selectable='single',
                    style_cell_conditional=[
                        {
                            'if': {'column_id': c},
                            'textAlign': 'left'
                        } for c in results_list[0]
                    ],
                    style_data_conditional=[
                        {
                            'if': {'row_index': 'odd'},
                            'backgroundColor': 'rgb(248, 248, 248)',
                        }
                    ],
                    style_header={
                        'backgroundColor': 'rgb(230, 230, 230)',
                        'fontWeight': 'bold'
                    },
                    css=[{'selector': '.row', 'rule': 'margin: 0'}],
                    style_table={
                        'overflowX': 'auto'
                    },
                    style_cell={
                        'overflow': 'hidden',
                        'textOverflow': 'ellipsis',
                        'maxWidth': 0,
                    },          
                    tooltip_data=[
                        {
                            column: {'value': str(value), 'type': 'markdown'}
                            for column, value in row.items()
                        } for row in results_list
                    ],
                    id='datatable',
                    page_size=20),

    return [table_obj]


@dash_app.callback([
                Output('massql_visualization', 'children')
              ],
              [
                  Input('datatable', 'derived_virtual_data'),
                  Input('datatable', 'derived_virtual_selected_rows'),
              ])
def draw_visualization(table_data, table_selected):
    try:
        selected_row = table_data[table_selected[0]]
    except:
        return ["Choose a MassQL Query"]

    import dash_sandbox

    massql_query = selected_row["MassQL Query"]

    render_list = dash_sandbox._render_parse(massql_query)

    param_dict = {}
    param_dict["QUERY"] = massql_query
    param_dict["workflow"] = "MSQL-NF"

    param_string = urllib.parse.quote(json.dumps(param_dict))
    gnps_url = "https://proteomics2.ucsd.edu/ProteoSAFe/index.jsp?&params={}".format(param_string)

    sandbox_url = "/?query={}".format(massql_query)

    query_row = dbc.Row([
        dbc.Col(
            html.A(
                dbc.Button("Try out in SandBox", color="primary"),
                href=sandbox_url,
                className="d-grid gap-2",
                target="_blank",
            )
        ),
        dbc.Col(
            html.A(
                dbc.Button("Use Query on Your Files", color="primary"),
                href=gnps_url,
                className="d-grid gap-2",
                target="_blank",
            )
        ),
    ]),

    render_list.insert(0, html.Br())
    render_list.insert(0, html.Div(query_row))
    render_list.insert(0, html.Br())

    return [render_list]
    



if __name__ == "__main__":
    dash_app.run_server(host="0.0.0.0", port=5000, debug=True)