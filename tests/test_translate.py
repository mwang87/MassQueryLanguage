
import sys
import os

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from massql import msql_translator

import json
import pytest

def test_translate():
    languages = ["korean", "chinese", "french", "german", "spanish", "portuguese", "english", "japanese", "italian"]

    for language in languages:
        # Writing out the queries and comparing
        test_queries_filename = os.path.join(os.path.dirname(__file__), "test_queries.txt")
        for line in open(test_queries_filename):
            test_query = line.rstrip()
            translation = msql_translator.translate_query(test_query, language=language)
            if "contact Ming" in translation:
                print("Not Implemented", test_query)
                print(translation)


def test_translate2():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=184.0739:TOLERANCEMZ=0.01:INTENSITYPERCENT=30:INTENSITYVALUE=500 AND \
MS2PROD=125.0004:TOLERANCEMZ=0.01:INTENSITYPERCENT=10:INTENSITYVALUE=1500 AND \
MS2PROD=104.1075:TOLERANCEMZ=0.01 AND \
MS2PROD=86.09697:TOLERANCEMZ=0.01:INTENSITYPERCENT=10:INTENSITYVALUE=2000 \
"
    translated = msql_translator.translate_query(query, language="english")
    print(translated)

def test_or_translate():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=(184.0739 OR 190)"
    translated = msql_translator.translate_query(query, language="english")
    print(translated)
    
def main():
    test_translate()
    #test_translate2()
    #test_or_translate()
    
if __name__ == "__main__":
    main()
