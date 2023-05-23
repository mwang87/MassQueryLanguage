import sys
import os

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from massql import msql_parser
import json
import pytest

def test_parse():
    # This test not only performs a parse, but also tries to compare it against a reference parse

    from pathvalidate import sanitize_filename
    import os
    import hashlib

    # Writing out the queries and comparing
    current_dir = os.path.dirname(__file__)
    test_parses_dir = os.path.join(current_dir, "test_parses")
    reference_parses_dir = os.path.join(current_dir, "reference_parses")    

    os.makedirs(test_parses_dir, exist_ok=True)

    test_queries_filename = os.path.join(current_dir, "test_queries.txt")
    for line in open(test_queries_filename):
        test_query = line.rstrip()
        print(test_query)
        output_parse = msql_parser.parse_msql(test_query)

        hash_object = hashlib.md5(test_query.encode("ascii"))
        hash_output = hash_object.hexdigest()

        json_filename = sanitize_filename(test_query).replace(" ", "_").replace("=", "_").replace("(", "_").replace(")", "_")[:50] + "___" +  hash_output + ".json"

        output_filename = os.path.join(test_parses_dir, json_filename)
        output_json_str = json.dumps(output_parse, sort_keys=True, indent=4)

        with open(output_filename, "w") as o:
            o.write(output_json_str)

        reference_filename = os.path.join(reference_parses_dir, json_filename)
        reference_string = open(reference_filename).read()

        try:
            assert(output_json_str == reference_string)
        except: 
            print("Assertion error", reference_filename)
            raise

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
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=X-formula(Fe)*2"

    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))

def test_variable_formula_parse2():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=2.0*(X - formula(Fe))"

    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))

def test_xrange_parse():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=2.0*(X - formula(Fe)) AND X=range(min=5, max=100)"

    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))

    query = "QUERY scaninfo(MS2DATA) WHERE MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE:INTENSITYVALUE=10000 \
AND \
MS1MZ=X+1:INTENSITYMATCH=Y*0.4:INTENSITYMATCHPERCENT=50:TOLERANCEPPM=10 AND MS1MZ=X+1.998:INTENSITYMATCH=Y*0.446:INTENSITYMATCHPERCENT=50:TOLERANCEPPM=10 AND X=range(min=300,max=900)"

    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))

def test_xdefect_parse():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=2.0*(X - formula(Fe)) AND \
                X=massdefect(min=0.1, max=0.2) AND X=range(min=5, max=100)"

    parsed_output = msql_parser.parse_msql(query)
    print(json.dumps(parsed_output, indent=4))

def test_ms2_synonyms():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=100"
    query2 = "QUERY scaninfo(MS2DATA) WHERE MS2MZ=100"

    parsed_output = msql_parser.parse_msql(query)
    parsed_output2 = msql_parser.parse_msql(query2)

    parsed_output["query"] = ""
    parsed_output2["query"] = ""

    assert(json.dumps(parsed_output) == json.dumps(parsed_output2))

def test_variable_parse():
    # This finds the sum of the MS1 of the MS2 spectrum with 
    query = "QUERY scaninfo(MS2DATA) WHERE MS1MZ=X AND MS2PREC=X AND MS2PROD=119.09"
    parse_obj = msql_parser.parse_msql(query)
    print(json.dumps(parse_obj, indent=4))

def test_ms2_or():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=(100 OR 104)"

    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)

def test_ms1_or():
    query = "QUERY scaninfo(MS1DATA) WHERE MS1MZ=(100 OR 104)"

    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)
    assert(len(parsed_output["conditions"][0]["value"]) == 2)

def test_ms1_multiple_or():
    query = "QUERY scaninfo(MS1DATA) WHERE MS1MZ=(100 OR 104 OR 106 OR 108)"

    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)
    assert(len(parsed_output["conditions"][0]["value"]) == 4)

def test_ms1_multiple_or_with_variable():
    query = "QUERY scaninfo(MS1DATA) WHERE MS1MZ=(X OR X+2 OR X+4 OR X+6)"

    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)
    assert(len(parsed_output["conditions"][0]["value"]) == 4)

def test_mobility():
    query = "QUERY scaninfo(MS2DATA) WHERE MOBILITY=range(min=100, max=500)"
    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)

    assert(parsed_output["conditions"][0]["min"] == 100)

def test_mobility_variables():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PREC=X AND MOBILITY=range(min=X/100, max=2*X/100)"
    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)


def test_negation():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PREC=227:EXCLUDED"
    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)

    assert(parsed_output["conditions"][0]["qualifiers"]["qualifierexcluded"]["name"] == "qualifierexcluded")

def test_wildcard():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=ANY:MASSDEFECT=massdefect(min=0.8, max=0.9)"
    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)
    assert(parsed_output["conditions"][0]["qualifiers"]["qualifiermassdefect"]["min"] == 0.8)

    query = "QUERY scaninfo(MS2DATA) WHERE MS2PREC=X:MASSDEFECT=massdefect(min=0.9, max=0.99) AND MOBILITY=range(min=X*0.0006775+0.40557, max=X*0.00078231+0.48817) AND X=massdefect(min=0.9, max=0.99)"
    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)


def test_cardinality():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=(100 OR 104):CARDINALITY=range(min=1, max=50)"
    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)
    assert(parsed_output["conditions"][0]["qualifiers"]["qualifiercardinality"]["min"] == 1.0)

    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=(100 OR 104):MATCHCOUNT=range(min=1, max=50)"
    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)
    assert(parsed_output["conditions"][0]["qualifiers"]["qualifiercardinality"]["min"] == 1.0)

def test_or_cardinality():
    query = """
        QUERY scaninfo(MS2DATA) WHERE 
        MS2PROD=(120.08078 OR 86.09643 OR 70.06513 OR 72.08078 OR 159.09167 OR 136.07569):CARDINALITY=range(min=2, max=2)
    """

    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)


def test_repeat_parse():
    query = """
        QUERY scaninfo(MS2DATA) WHERE MS2PROD=(formula(C3H5O2C2H6) + multiple(mz=formula(CH2),min=2, max=60) )
    """

    parsed_output = msql_parser.parse_msql(query)
    print(parsed_output)



def main():
    test_repeat_parse()
    #test_ms1_multiple_or_with_variable()
    #test_xrange_parse()
    #test_parse()
    #test_comment_parse()
    #test_number_expression_parse()
    #test_formula_expression_parse()
    #test_aminoacids_expression_parse()
    #test_peptide_expression_parse()
    #test_formula2_expression_parse()
    #test_variable_formula_parse()
    #test_variable_formula_parse2()
    #test_ms2_synonyms()
    #test_visualize_parse()
    #test_xdefect_parse()
    #test_ms2_or()
    #test_ms1_multiple_or()
    #test_ms1_multiple_or_with_variable()
    #test_mobility()
    #test_mobility_variables()
    #test_negation()
    #test_wildcard()
    #test_ms1_multiple_or()
    #test_cardinality()
    #test_or_cardinality()



if __name__ == "__main__":
    main()