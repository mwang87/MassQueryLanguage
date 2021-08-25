import pandas as pd
from py_expression_eval import Parser
math_parser = Parser()

def _get_mz_tolerance(qualifiers, mz):
    if qualifiers is None:
        return 0.1

    if "qualifierppmtolerance" in qualifiers:
        ppm = qualifiers["qualifierppmtolerance"]["value"]
        mz_tol = abs(ppm * mz / 1000000)
        return mz_tol

    if "qualifiermztolerance" in qualifiers:
        return qualifiers["qualifiermztolerance"]["value"]

    return 0.1

def _get_minintensity(qualifier):
    """
    Returns absolute min and relative min

    Args:
        qualifier ([type]): [description]

    Returns:
        [type]: [description]
    """

    min_intensity = 0
    min_percent_intensity = 0
    min_tic_percent_intensity = 0
    

    if qualifier is None:
        min_intensity = 0
        min_percent_intensity = 0

        return min_intensity, min_percent_intensity, min_tic_percent_intensity
    
    if "qualifierintensityvalue" in qualifier:
        min_intensity = float(qualifier["qualifierintensityvalue"]["value"])

    if "qualifierintensitypercent" in qualifier:
        min_percent_intensity = float(qualifier["qualifierintensitypercent"]["value"]) / 100

    if "qualifierintensityticpercent" in qualifier:
        min_tic_percent_intensity = float(qualifier["qualifierintensityticpercent"]["value"]) / 100

    # since the subsequent comparison is a strict greater than, if people set it to 100, then they won't get anything. 
    min_percent_intensity = min(min_percent_intensity, 0.99)

    return min_intensity, min_percent_intensity, min_tic_percent_intensity

def _set_intensity_register(ms_filtered_df, register_dict, condition):
    if "qualifiers" in condition:
        if "qualifierintensityreference" in condition["qualifiers"]:
            qualifier_variable = condition["qualifiers"]["qualifierintensitymatch"]["value"]

            grouped_df = ms_filtered_df.groupby("scan").sum().reset_index()
            for grouped_scan in grouped_df.to_dict(orient="records"):
                # Saving into the register
                key = "scan:{}:variable:{}".format(grouped_scan["scan"], qualifier_variable)
                register_dict[key] = grouped_scan["i"]
    return

def _filter_intensitymatch(ms_filtered_df, register_dict, condition):
    if "qualifiers" in condition:
        if "qualifierintensitymatch" in condition["qualifiers"] and \
            "qualifierintensitytolpercent" in condition["qualifiers"]:
            qualifier_expression = condition["qualifiers"]["qualifierintensitymatch"]["value"]
            qualifier_variable = qualifier_expression[0] #TODO: This assumes the variable is the first character in the expression, likely a bad assumption

            grouped_df = ms_filtered_df.groupby("scan").sum().reset_index()

            filtered_grouped_scans = []
            for grouped_scan in grouped_df.to_dict(orient="records"):
                # Reading from the register
                key = "scan:{}:variable:{}".format(grouped_scan["scan"], qualifier_variable)

                if key in register_dict:
                    register_value = register_dict[key]                    
                    evaluated_new_expression = math_parser.parse(qualifier_expression).evaluate({
                        qualifier_variable : register_value
                    })

                    min_match_intensity, max_match_intensity = _get_intensitymatch_range(condition["qualifiers"], evaluated_new_expression)

                    scan_intensity = grouped_scan["i"]

                    #print(key, scan_intensity, qualifier_expression, min_match_intensity, max_match_intensity, grouped_scan)

                    if scan_intensity > min_match_intensity and \
                        scan_intensity < max_match_intensity:
                        filtered_grouped_scans.append(grouped_scan)
                else:
                    # Its not in the register, which means we don't find it
                    continue
            return pd.DataFrame(filtered_grouped_scans)

    return ms_filtered_df

def _get_intensitymatch_range(qualifiers, match_intensity):
    """
    Matching the intensity range

    Args:
        qualifiers ([type]): [description]
        match_intensity ([type]): [description]

    Returns:
        [type]: [description]
    """

    min_intensity = 0
    max_intensity = 0

    if "qualifierintensitytolpercent" in qualifiers:
        tolerance_percent = qualifiers["qualifierintensitytolpercent"]["value"]
        tolerance_value = float(tolerance_percent) / 100 * match_intensity
        
        min_intensity = match_intensity - tolerance_value
        max_intensity = match_intensity + tolerance_value

    return min_intensity, max_intensity

def ms2prod_condition(condition, ms1_df, ms2_df, reference_conditions_register):
    """
    Filters the MS1 and MS2 data based upon MS2 peak conditions

    Args:
        condition ([type]): [description]
        ms1_df ([type]): [description]
        ms2_df ([type]): [description]
        reference_conditions_register ([type]): Edits this in place

    Returns:
        ms1_df ([type]): [description]
        ms2_df ([type]): [description]
    """

    if len(ms2_df) == 0:
        return ms1_df, ms2_df

    ms2_list = []
    for mz in condition["value"]:
        mz_tol = _get_mz_tolerance(condition.get("qualifiers", None), mz)
        mz_min = mz - mz_tol
        mz_max = mz + mz_tol

        min_int, min_intpercent, min_tic_percent_intensity = _get_minintensity(condition.get("qualifiers", None))

        ms2_filtered_df = ms2_df[(ms2_df["mz"] > mz_min) & 
                                (ms2_df["mz"] < mz_max) & 
                                (ms2_df["i"] > min_int) & 
                                (ms2_df["i_norm"] > min_intpercent) & 
                                (ms2_df["i_tic_norm"] > min_tic_percent_intensity)]

        # Setting the intensity match register
        _set_intensity_register(ms2_filtered_df, reference_conditions_register, condition)

        # Applying the intensity match
        ms2_filtered_df = _filter_intensitymatch(ms2_filtered_df, reference_conditions_register, condition)

        ms2_list.append(ms2_filtered_df)

    if len(ms2_list) == 1:
        ms2_filtered_df = ms2_list[0]
    else:
        ms2_filtered_df = pd.concat(ms2_list)

    if len(ms2_filtered_df) == 0:
       return pd.DataFrame(), pd.DataFrame()
    
    # Filtering the actual data structures
    filtered_scans = set(ms2_filtered_df["scan"])
    ms2_df = ms2_df[ms2_df["scan"].isin(filtered_scans)]

    # Filtering the MS1 data now
    ms1_scans = set(ms2_df["ms1scan"])
    ms1_df = ms1_df[ms1_df["scan"].isin(ms1_scans)]

    return ms1_df, ms2_df

def ms2nl_condition(condition, ms1_df, ms2_df, reference_conditions_register):
    """
    Filters the MS1 and MS2 data based upon MS2 neutral loss conditions

    Args:
        condition ([type]): [description]
        ms1_df ([type]): [description]
        ms2_df ([type]): [description]
        reference_conditions_register ([type]): Edits this in place

    Returns:
        ms1_df ([type]): [description]
        ms2_df ([type]): [description]
    """

    if len(ms2_df) == 0:
        return ms1_df, ms2_df

    ms2_list = []
    for mz in condition["value"]:
        mz_tol = _get_mz_tolerance(condition.get("qualifiers", None), mz) #TODO: This is incorrect logic if it comes to PPM accuracy
        nl_min = mz - mz_tol
        nl_max = mz + mz_tol

        min_int, min_intpercent, min_tic_percent_intensity = _get_minintensity(condition.get("qualifiers", None))

        ms2_filtered_df = ms2_df[
            ((ms2_df["precmz"] - ms2_df["mz"]) > nl_min) & 
            ((ms2_df["precmz"] - ms2_df["mz"]) < nl_max) &
            (ms2_df["i"] > min_int) & 
            (ms2_df["i_norm"] > min_intpercent) & 
            (ms2_df["i_tic_norm"] > min_tic_percent_intensity)
        ]

        # Setting the intensity match register
        _set_intensity_register(ms2_filtered_df, reference_conditions_register, condition)

        # Applying the intensity match
        ms2_filtered_df = _filter_intensitymatch(ms2_filtered_df, reference_conditions_register, condition)

        ms2_list.append(ms2_filtered_df)

    if len(ms2_list) == 1:
        ms2_filtered_df = ms2_list[0]
    else:
        ms2_filtered_df = pd.concat(ms2_list)

    if len(ms2_filtered_df) == 0:
       return pd.DataFrame(), pd.DataFrame()

    # Filtering the actual data structures
    filtered_scans = set(ms2_filtered_df["scan"])
    ms2_df = ms2_df[ms2_df["scan"].isin(filtered_scans)]

    # Filtering the MS1 data now
    ms1_scans = set(ms2_df["ms1scan"])
    ms1_df = ms1_df[ms1_df["scan"].isin(ms1_scans)]

    return ms1_df, ms2_df

def ms2prec_condition(condition, ms1_df, ms2_df, reference_conditions_register):
    """
    Filters the MS1 and MS2 data based upon MS2 precursor conditions

    Args:
        condition ([type]): [description]
        ms1_df ([type]): [description]
        ms2_df ([type]): [description]
        reference_conditions_register ([type]): Edits this in place

    Returns:
        ms1_df ([type]): [description]
        ms2_df ([type]): [description]
    """

    if len(ms2_df) == 0:
        return ms1_df, ms2_df

    ms1_list = []
    ms2_list = []
    for mz in condition["value"]:
        mz_tol = _get_mz_tolerance(condition.get("qualifiers", None), mz)
        mz_min = mz - mz_tol
        mz_max = mz + mz_tol

        ms2_filtered_df = ms2_df[(
            ms2_df["precmz"] > mz_min) & 
            (ms2_df["precmz"] < mz_max)
        ]

        # Filtering the MS1 data now
        ms1_scans = set(ms2_df["ms1scan"])
        ms1_filtered_df = ms1_df[ms1_df["scan"].isin(ms1_scans)]

        ms1_list.append(ms1_filtered_df)
        ms2_list.append(ms2_filtered_df)
    
    if len(ms1_list) == 1:
        return ms1_list[0], ms2_list[0]

    ms1_df = pd.concat(ms1_list)
    ms2_df = pd.concat(ms2_list)

    return ms1_df, ms2_df

def ms1_condition(condition, ms1_df, ms2_df, reference_conditions_register):
    """
    Filters the MS1 and MS2 data based upon MS1 peak conditions

    Args:
        condition ([type]): [description]
        ms1_df ([type]): [description]
        ms2_df ([type]): [description]
        reference_conditions_register ([type]): Edits this in place

    Returns:
        ms1_df ([type]): [description]
        ms2_df ([type]): [description]
    """
    if len(ms1_df) == 0:
        return ms1_df, ms2_df

    ms1_list = []
    for mz in condition["value"]:
        mz_tol = _get_mz_tolerance(condition.get("qualifiers", None), mz)
        mz_min = mz - mz_tol
        mz_max = mz + mz_tol

        min_int, min_intpercent, min_tic_percent_intensity = _get_minintensity(condition.get("qualifiers", None))
        ms1_filtered_df = ms1_df[
            (ms1_df["mz"] > mz_min) & 
            (ms1_df["mz"] < mz_max) & 
            (ms1_df["i"] > min_int) & 
            (ms1_df["i_norm"] > min_intpercent) & 
            (ms1_df["i_tic_norm"] > min_tic_percent_intensity)]

        # Setting the intensity match register
        _set_intensity_register(ms1_filtered_df, reference_conditions_register, condition)

        # Applying the intensity match
        ms1_filtered_df = _filter_intensitymatch(ms1_filtered_df, reference_conditions_register, condition)

        ms1_list.append(ms1_filtered_df)
    
    if len(ms1_list) == 1:
        ms1_filtered_df = ms1_list[0]
    else:
        ms1_filtered_df = pd.concat(ms1_list)

    if len(ms1_filtered_df) == 0:
       return pd.DataFrame(), pd.DataFrame()

    # Filtering the actual data structures
    filtered_scans = set(ms1_filtered_df["scan"])
    ms1_df = ms1_df[ms1_df["scan"].isin(filtered_scans)]

    if "ms1scan" in ms2_df:
        ms2_df = ms2_df[ms2_df["ms1scan"].isin(filtered_scans)]

    return ms1_df, ms2_df

    
