import msql_parser
import msql_engine
import msql_translator
import msql_fileloading
import json
import pytest

def test_translate():

    # Writing out the queries and comparing
    for line in open("test_queries.txt"):
        test_query = line.rstrip()
        msql_translator.translate_query(test_query)
        
    
def main():
    test_translate()
    
if __name__ == "__main__":
    main()
