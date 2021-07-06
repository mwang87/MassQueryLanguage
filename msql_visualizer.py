import msql_parser
import msql_engine
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from py_expression_eval import Parser
math_parser = Parser()


def visualize_query(query, variable_x=500, variable_y=1, precursor_mz=800, ms1_peaks=None, ms2_peaks=None):
    """
    This function creates a plotly visualization. If ms1 and ms2 peaks are included, we will plot them along with it. 

    Args:
        query ([type]): [description]
        variable_x (int, optional): [description]. Defaults to 500.
        variable_y (int, optional): [description]. Defaults to 1.
        precursor_mz (int, optional): [description]. Defaults to 800.
        ms1_peaks ([type], optional): [description]. Defaults to None.
        ms2_peaks ([type], optional): [description]. Defaults to None.

    Returns:
        [type]: [description]
    """

    parsed_query = msql_parser.parse_msql(query)

    # Cleaning up variables
    for condition in parsed_query["conditions"]:
        # Setting m/z variables
        for i, value in enumerate(condition["value"]):
            try:
                # Checking if X is in any string
                if "X" in value:
                    condition["value"][i] = math_parser.parse(value ).evaluate({
                                "X" : variable_x
                            })    
            except:
                pass

        # Setting intensity variables
        if "qualifiers" in condition:
            if "qualifierintensitymatch" in condition["qualifiers"]:
                value = condition["qualifiers"]["qualifierintensitymatch"]["value"]
                condition["qualifiers"]["qualifierintensitymatch"]["value"] = math_parser.parse(value).evaluate({
                                "Y" : variable_y
                            })                

    ms1_fig = go.Figure()
    ms2_fig = go.Figure()

    if ms1_peaks is not None:
        max_int = max([peak[1] for peak in ms2_peaks])
        # Drawing the spectrum object
        mzs = [peak[0] for peak in ms1_peaks]
        ints = [peak[1]/max_int for peak in ms1_peaks]
        neg_ints = [intensity * -1 for intensity in ints]

        ms1_fig = go.Figure(
            data=go.Scatter(x=mzs, y=ints, 
                mode='markers+text',
                marker=dict(size=0.00001),
                error_y=dict(
                    symmetric=False,
                    arrayminus=[0]*len(neg_ints),
                    array=neg_ints,
                    width=0
                ),
                hoverinfo="x",
                textposition="top right"
            )
        )


    if ms2_peaks is not None:
        max_int = max([peak[1] for peak in ms2_peaks])
        # Drawing the spectrum object
        mzs = [peak[0] for peak in ms2_peaks]
        ints = [peak[1]/max_int for peak in ms2_peaks]
        neg_ints = [intensity * -1 for intensity in ints]

        ms2_fig = go.Figure(
            data=go.Scatter(x=mzs, y=ints, 
                mode='markers+text',
                marker=dict(size=0.00001),
                error_y=dict(
                    symmetric=False,
                    arrayminus=[0]*len(neg_ints),
                    array=neg_ints,
                    width=0
                ),
                hoverinfo="x",
                textposition="top right"
            )
        )

    for condition in parsed_query["conditions"]:
        print(condition)
        if condition["type"] == "ms2productcondition" and condition["conditiontype"] == "where":
            mz = condition["value"][0]
            mz_tol = msql_engine._get_mz_tolerance(condition.get("qualifiers", None), mz)

            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            intensity = 1

            if "qualifiers" in condition:
                if "qualifierintensitymatch" in condition["qualifiers"]:
                    intensity = condition["qualifiers"]["qualifierintensitymatch"]["value"]

            ms2_fig.add_shape(type="rect",
                x0=mz_min, y0=0, x1=mz_max, y1=intensity,
                line=dict(
                    color="Blue",
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

            intensity = 1

            if "qualifiers" in condition:
                if "qualifierintensitymatch" in condition["qualifiers"]:
                    intensity = condition["qualifiers"]["qualifierintensitymatch"]["value"]

            ms2_fig.add_shape(type="rect",
                x0=mz_min, y0=0, x1=mz_max, y1=intensity,
                line=dict(
                    color="Red",
                    width=2,
                )
            )

        if condition["type"] == "ms1mzcondition":
            mz = condition["value"][0]
            mz_tol = msql_engine._get_mz_tolerance(condition.get("qualifiers", None), mz)
            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            intensity = 1

            if "qualifiers" in condition:
                if "qualifierintensitymatch" in condition["qualifiers"]:
                    intensity = condition["qualifiers"]["qualifierintensitymatch"]["value"]

            ms1_fig.add_shape(type="rect",
                x0=mz_min, y0=0, x1=mz_max, y1=intensity,
                line=dict(
                    color="Blue",
                    width=2,
                )
            )

    # Set axes properties
    ms2_fig.update_xaxes(range=[0, 1000], showgrid=False)
    ms2_fig.update_yaxes(range=[0, 1.5])

    ms2_fig.update_layout(
        title="MS2 Query Visualization, Precursor m/z {}".format(precursor_mz),
        xaxis_title="m/z",
        yaxis_title="intensity",
    )

    ms1_fig.update_xaxes(range=[0, 1000], showgrid=False)
    ms1_fig.update_yaxes(range=[0, 1.5])

    ms1_fig.update_layout(
        title="MS1 Query Visualization",
        xaxis_title="m/z",
        yaxis_title="intensity",
    )

    return ms1_fig, ms2_fig