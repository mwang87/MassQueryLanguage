import msql_parser

def translate_query(query):
    parsed_query = msql_parser.parse_msql(query)

    sentences = []

    sentences.append(_translate_querytype(parsed_query["querytype"]))

    print(parsed_query)

    for condition in parsed_query["conditions"]:
        sentences.append(_translate_condition(condition))

    print(sentences)

    return "\n".join(sentences)


def _translate_querytype(querytype):
    # return information
    ms_level = "MS1"
    if querytype["datatype"] == "datams1data":
        ms_level = "MS1"
    if querytype["datatype"] == "datams2data":
        ms_level = "MS2"

    if querytype["function"] == "functionscaninfo":
        return "Getting the scan information on {}.".format(ms_level)

    return "Translator {} not implemented, contact Ming".format(querytype["function"])

def _translate_condition(condition):
    if "qualifiers" in condition:
        qualifier_string = " " + _translate_qualifiers(condition["qualifiers"])
    else:
        qualifier_string = ""

    print("XXX", qualifier_string)

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
            
    return " ".join(qualifier_phrases)



def _translate_qualifier(qualifier):
    if qualifier["name"] == "qualifierppmtolerance":
        return "with a {} PPM tolerance".format(qualifier["value"])

    return "Translator not implemented, contact Ming"