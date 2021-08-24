
import sys
import os

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from massql import msql_translator

import json
import pytest

def test_translate():
    languages = ["korean", "chinese", "french", "german", "spanish", "portuguese", "english"]

    for language in languages:
        # Writing out the queries and comparing
        test_queries_filename = os.path.join(os.path.dirname(__file__), "test_queries.txt")
        for line in open(test_queries_filename):
            test_query = line.rstrip()
            print(test_query, language)
            msql_translator.translate_query(test_query, language=language)
    
def main():
    test_translate()
    
if __name__ == "__main__":
    main()
