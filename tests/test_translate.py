
import sys
import os

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from massql import msql_translator

import json
import pytest

def test_translate():
    languages = ["english", "korean", "chinese", "french", "german", "spanish", "portuguese", "japanese"]

    for language in languages:
        # Writing out the queries and comparing
        test_queries_filename = os.path.join(os.path.dirname(__file__), "test_queries.txt")
        for line in open(test_queries_filename):
            test_query = line.rstrip()
            translation = msql_translator.translate_query(test_query, language=language)
            if "contact Ming" in translation:
                print("Not Implemented ", language, test_query)
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

def test_cardinality():
    query = "QUERY scaninfo(MS2DATA) WHERE MS2PROD=(58.06513 OR 60.04439 OR 70.06513 OR 72.08078 OR 74.06004 OR 84.04439 OR 84.08078 OR 86.09643 OR 87.05529 OR 88.0393 OR 88.07569 OR 100.11208 OR 101.07094 OR 101.10732 OR 102.05495 OR 102.09134 OR 104.05285 OR 110.07127 OR 114.12773 OR 115.08659 OR 115.12297 OR 116.0706 OR 118.0685 OR 120.08078 OR 124.08692 OR 129.10224 OR 129.11347 OR 129.13862 OR 130.08625 OR 132.08415 OR 134.09643 OR 136.07569 OR 138.10257 OR 143.12912 OR 148.11208 OR 150.09134 OR 157.14477 OR 159.09167 OR 164.10699 OR 173.10732 OR 187.12297):CARDINALITY=range(min=2,max=5):TOLERANCEPPM=10:INTENSITYPERCENT=5"
    translated = msql_translator.translate_query(query, language="english")
    print(translated)


def main():
    test_cardinality()
    #test_translate()
    #test_translate2()
    #test_or_translate()
    
if __name__ == "__main__":
    main()
