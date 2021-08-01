import msql_parser
import msql_engine
import msql_translator
import msql_visualizer
import msql_fileloading
import json
import pytest

def test_parse():
    # This test not only performs a parse, but also tries to compare it against a reference parse

    from pathvalidate import sanitize_filename
    import os
    import hashlib

    # Writing out the queries and comparing
    for line in open("test_queries.txt"):
        test_query = line.rstrip()
        print(test_query)
        output_parse = msql_parser.parse_msql(test_query)

        hash_object = hashlib.md5(test_query.encode("ascii"))
        hash_output = hash_object.hexdigest()

        json_filename = sanitize_filename(test_query).replace(" ", "_").replace("=", "_").replace("(", "_").replace(")", "_")[:50] + "___" +  hash_output + ".json"

        output_filename = os.path.join("test/test_parses", json_filename)
        output_json_str = json.dumps(output_parse, sort_keys=True, indent=4)

        with open(output_filename, "w") as o:
            o.write(output_json_str)

        reference_filename = os.path.join("test/reference_parses", json_filename)
        reference_string = open(reference_filename).read()

        assert(output_json_str == reference_string)

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
    test_parse()
    #test_comment_parse()
    #test_number_expression_parse()
    #test_formula_expression_parse()
    #test_aminoacids_expression_parse()
    #test_peptide_expression_parse()
    #test_formula2_expression_parse()
    test_variable_formula_parse()

if __name__ == "__main__":
    main()