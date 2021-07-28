import msql_parser

def translate_query(query):
    parsed_query = msql_parser.parse_msql(query)

    sentences = []
    sentences.append(_translate_querytype(parsed_query["querytype"]))

    if len(parsed_query["conditions"]) > 0:
        sentences.append("The following conditions are applied to find scans in the mass spec data.")

    for condition in parsed_query["conditions"]:
        sentences.append(_translate_condition(condition))

    return "\n".join(sentences)


def _translate_querytype(querytype):
    # return information
    ms_level = "MS1"
    if querytype["datatype"] == "datams1data":
        ms_level = "MS1"
    if querytype["datatype"] == "datams2data":
        ms_level = "MS2"

    if querytype["function"] == "functionscaninfo":
        return "Returning the scan information on {}.".format(ms_level)

    if querytype["function"] == "functionscansum":
        return "Returning the summed scan information on {}.".format(ms_level)

    return "Translator {} not implemented, contact Ming".format(querytype["function"])

def _translate_condition(condition):
    if "qualifiers" in condition:
        qualifier_string = " " + _translate_qualifiers(condition["qualifiers"])
    else:
        qualifier_string = ""

    if condition["type"] == "ms2productcondition":
        return "Finding MS2 peak at m/z {}{}.".format(condition["value"][0], qualifier_string) #TODO: add qualifiers

    if condition["type"] == "ms2neutrallosscondition":
        return "Finding MS2 neutral loss peak at m/z {}{}.".format(condition["value"][0], qualifier_string) #TODO: add qualifiers
    
    if condition["type"] == "ms1mzcondition":
        return "Finding MS1 peak at m/z {}{}.".format(condition["value"][0], qualifier_string) #TODO: add qualifiers
    
    if condition["type"] == "ms2precursorcondition":
        return "Finding MS2 spectra with a precursor m/z {}{}.".format(condition["value"][0], qualifier_string) #TODO: add qualifiers

    return "Translator {} not implemented, contact Ming".format(condition["type"])

def _translate_qualifiers(qualifiers):
    qualifier_phrases = []

    for qualifier in qualifiers:
        # These are keys, so looking them  up
        if "qualifier" in qualifier:
            qualifier_phrases.append(_translate_qualifier(qualifiers[qualifier]))
            
    return " and ".join(qualifier_phrases)



def _translate_qualifier(qualifier):
    if qualifier["name"] == "qualifierppmtolerance":
        return "a {} PPM tolerance".format(qualifier["value"])

    if qualifier["name"] == "qualifiermztolerance":
        return "a {} m/z tolerance".format(qualifier["value"])

    if qualifier["name"] == "qualifierintensitypercent":
        return "a minimum percent intensity relative to base peak of {}%".format(qualifier["value"])

    if qualifier["name"] == "qualifierintensityreference":
        return "this peak is used as the intensity reference for other peaks in the spectrum"

    if qualifier["name"] == "qualifierintensitymatch":
        return "an expected relative intensity to reference peak of {}".format(qualifier["value"]) #TODO: we should likely remove the Y or assume it 1.0

    if qualifier["name"] == "qualifierintensitytolpercent":
        return "accepting variability of {}% in relative intensity".format(qualifier["value"])

    return "Translator {} not implemented, contact Ming".format(qualifier["name"])