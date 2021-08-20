import msql_parser
import msql_engine
import msql_translator
import msql_fileloading
import json
import pytest

def test_translate():
    languages = ["arabic", "korean", "chinese", "french", "german", "spanish", "portuguese", "english"]

    for language in languages:
        # Writing out the queries and comparing
        for line in open("test_queries.txt"):
            test_query = line.rstrip()
            print(test_query, language)
            msql_translator.translate_query(test_query, language=language)
    
def main():
    test_translate()
    
if __name__ == "__main__":
    main()
