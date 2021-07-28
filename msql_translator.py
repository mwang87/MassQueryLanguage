import msql_parser

def translate_query(query):
    parsed_query = msql_parser.parse_msql(query)

    sentences = []

    sentences.append(_translate_querytype(parsed_query["querytype"]))

    for condition in parsed_query["conditions"]:
        sentences.append(_translate_condition(condition))

    print(parsed_query)
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
    if condition["type"] == "ms2productcondition":
        return "Finding MS2 peak at m/z {}.".format(condition["value"][0]) #TODO: add qualifiers

    if condition["type"] == "ms2neutrallosscondition":
        return "Finding MS2 neutral loss peak at m/z {}.".format(condition["value"][0]) #TODO: add qualifiers
    
    if condition["type"] == "ms1mzcondition":
        return "Finding MS1 peak at m/z {}.".format(condition["value"][0]) #TODO: add qualifiers
    
    if condition["type"] == "ms2precursorcondition":
        return "Finding MS2 spectra with a precursor m/z {}.".format(condition["value"][0]) #TODO: add qualifiers

    return "Translator {} not implemented, contact Ming".format(condition["type"])