import msql_parser
import msql_engine
import plotly.graph_objects as go

from py_expression_eval import Parser
math_parser = Parser()


def visualize_query(query, variable_x=500, variable_y=1, precursor_mz=800):
    parsed_query = msql_parser.parse_msql(query)

    # Cleaning up variables
    for condition in parsed_query["conditions"]:
        for i, value in enumerate(condition["value"]):
            try:
                # Checking if X is in any string
                if "X" in value:
                    condition["value"][i] = math_parser.parse(value ).evaluate({
                                "X" : variable_x
                            })
            except:
                pass

    fig = go.Figure()

    for condition in parsed_query["conditions"]:
        print(condition)
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
                )
            )

        if condition["type"] == "ms2neutrallosscondition" and condition["conditiontype"] == "where":
            mz = condition["value"][0]
            mz_tol = msql_engine._get_mz_tolerance(condition.get("qualifiers", None), mz)
            nl_min = mz - mz_tol
            nl_max = mz + mz_tol

            mz_min = precursor_mz - nl_max
            mz_max = precursor_mz - nl_min

            fig.add_shape(type="rect",
                x0=mz_min, y0=0, x1=mz_max, y1=1,
                line=dict(
                    color="Red",
                    width=2,
                )
            )


    # Set axes properties
    fig.update_xaxes(range=[0, 1000], showgrid=False)
    fig.update_yaxes(range=[0, 1])

    fig.update_layout(
        title="Query Visualization, Precursor m/z {}".format(precursor_mz),
        xaxis_title="m/z",
        yaxis_title="intensity",
    )

    return fig