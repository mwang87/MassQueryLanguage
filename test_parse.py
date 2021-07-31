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

def main():
    test_comment_parse()

if __name__ == "__main__":
    main()