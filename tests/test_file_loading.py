import sys
import os

# Making sure the root is in the path, kind of a hack
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from massql import msql_fileloading

import json
import pytest

def test_improper_file():
    with pytest.raises(Exception):
        msql_fileloading.load_file('file.cdf')