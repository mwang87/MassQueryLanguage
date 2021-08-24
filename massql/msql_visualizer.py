from massql import msql_parser
from massql import msql_engine
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
        if "value" in condition:
            for i, value in enumerate(condition["value"]):
                try:
                    # Checking if X is in any string
                    if "X" in value:
                        condition["value"][i] = math_parser.parse(value).evaluate({
                                    "X" : variable_x
                                })    
                except:
                    pass

        # Setting intensity variables
        if "qualifiers" in condition:
            if "qualifierintensitymatch" in condition["qualifiers"]:
                value = condition["qualifiers"]["qualifierintensitymatch"]["value"]
                condition["qualifiers"]["qualifierintensitymatch"]["value"] = math_parser.parse(value).evaluate({
                                "Y" : variable_y,
                                "X" : variable_x
                            })

    ms1_fig = go.Figure()
    ms2_fig = go.Figure()

    ms1_min_x_axis = 0
    ms1_max_x_axis = 1000

    ms2_min_x_axis = 0
    ms2_max_x_axis = 1000

    if ms1_peaks is not None:
        max_int = max([peak[1] for peak in ms1_peaks])
        # Drawing the spectrum object
        mzs = [peak[0] for peak in ms1_peaks]
        ints = [peak[1]/max_int for peak in ms1_peaks]
        neg_ints = [intensity * -1 for intensity in ints]

        ms1_max_x_axis = max(ms1_max_x_axis, max(mzs))

        # Hover data
        hover_labels = ["{:.4f} m/z, {:.2f} int".format(mzs[i], ints[i]) for i in range(len(mzs))]

        ms1_fig = go.Figure(
            data=go.Scatter(x=mzs, y=ints, 
                mode='markers',
                marker=dict(size=0.00001),
                error_y=dict(
                    symmetric=False,
                    arrayminus=[0]*len(neg_ints),
                    array=neg_ints,
                    width=0
                ),
                text=hover_labels,
                textposition="top right"
            )
        )


    if ms2_peaks is not None:
        max_int = max([peak[1] for peak in ms2_peaks])
        # Drawing the spectrum object
        mzs = [peak[0] for peak in ms2_peaks]
        ints = [peak[1]/max_int for peak in ms2_peaks]
        neg_ints = [intensity * -1 for intensity in ints]

        ms2_max_x_axis = max(ms2_max_x_axis, max(mzs))

        # Hover data
        hover_labels = ["{:.4f} m/z, {:.3f} int".format(mzs[i], ints[i]) for i in range(len(mzs))]

        ms2_fig = go.Figure(
            data=go.Scatter(x=mzs, y=ints, 
                mode='markers',
                marker=dict(size=0.00001),
                error_y=dict(
                    symmetric=False,
                    arrayminus=[0]*len(neg_ints),
                    array=neg_ints,
                    width=0
                ),
                text=hover_labels,
                textposition="top right"
            )
        )

    for condition in parsed_query["conditions"]:
        if condition["conditiontype"] != "where":
            continue

        if condition["type"] == "ms2productcondition" and condition["conditiontype"] == "where":
            mz = condition["value"][0]
            mz_tol = msql_engine._get_mz_tolerance(condition.get("qualifiers", None), mz)

            mz_min = mz - mz_tol
            mz_max = mz + mz_tol

            intensity = 1

            if "qualifiers" in condition:
                if "qualifierintensitymatch" in condition["qualifiers"]:
                    intensity = condition["qualifiers"]["qualifierintensitymatch"]["value"]

            # Draw the bounds of the for the MS2 Product
            ms2_fig.add_shape(type="rect",
                x0=mz_min, y0=0, x1=mz_max, y1=intensity,
                line=dict(
                    color="Green",
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
        
        if condition["type"] == "xcondition":
            print(condition)
            ms1_fig.add_shape(type="line",
                x0=condition["min"], y0=0, x1=condition["min"], y1=1,
                line=dict(
                    color="pink",
                    width=2,
                    dash="dot",
                )
            )

            ms1_fig.add_shape(type="line",
                x0=condition["max"], y0=0, x1=condition["max"], y1=1,
                line=dict(
                    color="pink",
                    width=2,
                    dash="dot",
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
                    color="Green",
                    width=2,
                )
            )

            # Determining if we should draw intensity bounds
            if "qualifiers" in condition:
                if "qualifierintensitytolpercent" in condition["qualifiers"]:
                    percent_tolerance = condition["qualifiers"]["qualifierintensitytolpercent"]["value"]
                    percent_tolerance = percent_tolerance / 100
                    min_intensity = intensity - intensity * percent_tolerance
                    max_intensity = intensity + intensity * percent_tolerance
                    intensity_gap = max_intensity - min_intensity
                    mz_gap = mz_max - mz_min

                    # Top and bottom bounds

                    ms1_fig.add_shape(type="line",
                        x0=mz_min, y0=min_intensity, x1=mz_max, y1=min_intensity,
                        line=dict(
                            color="purple",
                            width=2,
                            dash="dot",
                        )
                    )

                    ms1_fig.add_shape(type="line",
                        x0=mz_min, y0=max_intensity, x1=mz_max, y1=max_intensity,
                        line=dict(
                            color="purple",
                            width=2,
                            dash="dot",
                        )
                    )

                    # Drawing arrows
                    
                    # Down Arrow
                    ms1_fig.add_annotation(
                        x=mz_min + mz_gap / 5,  # arrows' head
                        y=max_intensity - intensity_gap / 4,  # arrows' head
                        ax=mz_min + mz_gap / 5,  # arrows' tail
                        ay=max_intensity,  # arrows' tail
                        xref='x',
                        yref='y',
                        axref='x',
                        ayref='y',
                        text='',  # if you want only the arrow
                        showarrow=True,
                        arrowhead=3,
                        arrowsize=1,
                        arrowwidth=1,
                        arrowcolor='purple'
                    )

                    # Up Arrow
                    ms1_fig.add_annotation(
                        x=mz_min + mz_gap / 5,  # arrows' head
                        y=min_intensity + intensity_gap / 4,  # arrows' head
                        ax=mz_min + mz_gap / 5,  # arrows' tail
                        ay=min_intensity,  # arrows' tail
                        xref='x',
                        yref='y',
                        axref='x',
                        ayref='y',
                        text='',  # if you want only the arrow
                        showarrow=True,
                        arrowhead=3,
                        arrowsize=1,
                        arrowwidth=1,
                        arrowcolor='purple'
                    )

                if "qualifierintensitypercent" in condition["qualifiers"]:
                    value = condition["qualifiers"]["qualifierintensitypercent"]["value"] / 100
                    min_intensity = value
                    mz_gap = mz_max - mz_min

                    ms1_fig.add_shape(type="line",
                        x0=mz_min, y0=value, x1=mz_max, y1=value,
                        line=dict(
                            color="red",
                            width=2,
                            dash="dot",
                        )
                    )

                    # Up Arrow
                    ms1_fig.add_annotation(
                        x=mz_min + mz_gap / 5,  # arrows' head
                        y=min_intensity + 0.2 * min_intensity,  # arrows' head
                        ax=mz_min + mz_gap / 5,  # arrows' tail
                        ay=min_intensity,  # arrows' tail
                        xref='x',
                        yref='y',
                        axref='x',
                        ayref='y',
                        text='',  # if you want only the arrow
                        showarrow=True,
                        arrowhead=3,
                        arrowsize=1,
                        arrowwidth=1,
                        arrowcolor='red'
                    )


    # Set axes properties
    ms2_fig.update_xaxes(range=[ms2_min_x_axis, ms2_max_x_axis], showgrid=False)
    ms2_fig.update_yaxes(range=[0, 1.5])

    ms2_fig.update_layout(
        title="MS2 Query Visualization, Precursor m/z {}".format(precursor_mz),
        xaxis_title="m/z",
        yaxis_title="intensity",
    )

    # Setting axes properties
    ms1_fig.update_xaxes(range=[ms1_min_x_axis, ms1_max_x_axis], showgrid=False)
    ms1_fig.update_yaxes(range=[0, 1.5])

    ms1_fig.update_layout(
        title="MS1 Query Visualization",
        xaxis_title="m/z",
        yaxis_title="intensity",
    )

    return ms1_fig, ms2_fig