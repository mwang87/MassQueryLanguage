import msql_parser
import msql_engine
import plotly.graph_objects as go

def visualize_query(query, variable_x=500, variable_y=1):
    parsed_query = msql_parser.parse_msql(query)

    # Cleaning up variables

    fig = go.Figure()

    for condition in parsed_query["conditions"]:
        if condition["type"] == "ms2productcondition" and condition["conditiontype"] == "where":
            mz = condition["value"][0]
            mz_tol = msql_engine._get_mz_tolerance(condition.get("qualifiers", None), mz)

            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            fig.add_shape(type="rect",
                x0=mz_min, y0=0, x1=mz_max, y1=1,
                line=dict(
                    color="RoyalBlue",
                    width=2,
                ),
                fillcolor="LightSkyBlue",
            )

            print(condition)

    # Set axes properties
    fig.update_xaxes(range=[0, 1000], showgrid=False)
    fig.update_yaxes(range=[0, 1])


    return fig