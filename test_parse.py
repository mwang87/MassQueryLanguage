import msql_parser
import msql_engine
import msql_translator
import msql_visualizer
import msql_fileloading
import json
import pytest

def test_parse():        
    for line in open("test_queries.txt"):
        test_query = line.rstrip()
        print(test_query)
        msql_parser.parse_msql(test_query)

def test_comment_parse():
    query = """
    # COMMENT
    QUERY scaninfo(MS1DATA) # COMMENT2
    """

    parsed_output = msql_parser.parse_msql(query)

    print(parsed_output)

def test_number_expression_parse():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=157.0857+10"
    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))

    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=16.70857*10 +(0)"
    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))

    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=1670.857/10 +(0)"
    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))

def test_formula_expression_parse():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=formula(CH2)+14"
    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))
    assert(parsed_output["conditions"][0]["value"][0] > 28)

def test_formula2_expression_parse():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=formula(Fe)"
    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))
    assert(parsed_output["conditions"][0]["value"][0] > 28)

def test_aminoacids_expression_parse():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=aminoaciddelta(G)"
    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)
    print(json.dumps(parsed_output, indent=4))
    assert(parsed_output["conditions"][0]["value"][0] > 57)
    assert(parsed_output["conditions"][0]["value"][0] < 58)

def test_peptide_expression_parse():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=peptide(G, charge=1, ion=y)"
    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)
    print(json.dumps(parsed_output, indent=4))

    assert(parsed_output["conditions"][0]["value"][0] > 76)
    assert(parsed_output["conditions"][0]["value"][0] < 77)

def test_variable_formula_parse():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=X-formula(Fe)"

    parsed_output = msql_parser.parse_msql(query)

def main():
    #test_comment_parse()
    #test_number_expression_parse()
    #test_formula_expression_parse()
    #test_aminoacids_expression_parse()
    #test_peptide_expression_parse()
    #test_formula2_expression_parse()
    test_variable_formula_parse()

if __name__ == "__main__":
    main()