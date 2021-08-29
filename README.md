# Mass Spec Query Languge

[![Unit Testing](https://github.com/mwang87/MassQueryLanguage/actions/workflows/test-unit.yml/badge.svg)](https://github.com/mwang87/MassQueryLanguage/actions/workflows/test-unit.yml)
[![NF Workflow Testing](https://github.com/mwang87/MassQueryLanguage/actions/workflows/test-workflow.yml/badge.svg)](https://github.com/mwang87/MassQueryLanguage/actions/workflows/test-workflow.yml)

The Mass Spec Query Langauge (MassQL) is a domain specific language meant to be a succinct way to 
express a query in a mass spectrometry centric fashion. It is inspired by SQL, 
but it attempts to bake in assumptions of mass spectrometry to make querying much more
natural for mass spectrometry users. Broadly we attempt to design it according to several principles:

1. Expressiveness - Capture complex mass spectrometry patterns that the community would like to look for
1. Precision - Exactly prescribe how to find data without ambiguity
1. Relatively Natural - MassQL should be relatively easy to read and write and even use as a way to communicate ideas about mass spectrometry, you know like a language. 

## Repository Structure

This is the repository to define the language and reference implementation. This contains several parts

1. Language Grammar
1. Reference Implementation Python API
1. Commandline Utility to execute
1. NextFlow Workflow For Large Scale Analysis
1. ProteoSAFe workflow
1. Dash interactive exploration

## Developers/Contact

Mingxun Wang is the main creator and developer of MassQL. Contact me for contributing or using it!
## Language Specification/Documentation

Checkout specifics for the langauge, examples, and design patterns at the documentation. 

[Documentation Link](https://mwang87.github.io/MassQueryLanguage_Documentation/)


## Python API

To install massql

```
pip install massql
```

Here is the most basic operation you can do

```
from massql import msql_engine

results_df = msql_engine.process_query(input_query, input_filename)
```

If you want to push in a data frame you already have, you can specify it
```
from massql import msql_engine
from massql import msql_fileloading

# Loading Data
ms1_df, ms2_df = msql_fileloading.load_data(input_filename)

# Executing Query
results_df = msql_engine.process_query(input_query, input_filename, ms1_df=ms1_df, ms2_df=ms2_df)
```

## Command Line Tool

You can use the command line tool ```massql``` to query things or put things into a pipeline. 

A few examples of what you can do

```
massql test.mzML "QUERY scaninfo(MS2DATA)" --output_file results.tsv
```

## Web API

### API Version

```/api```

### Parsing query into intermediate JSON string

```/parse?query=<query string>```

[Example Link](https://msql.ucsd.edu/parse?query=QUERY%20MS2DATA%20WHERE%20MS1MZ=100)

### Visualization of Query

Visualization image of MS1 spectra

```/visualize/ms1```

[Example Link](https://msql.ucsd.edu/visualize/ms1?query=QUERY+scaninfo%28MS1DATA%29+WHERE+MS1MZ%3DX%3ATOLERANCEMZ%3D0.1%3AINTENSITYPERCENT%3D25%3AINTENSITYMATCH%3DY%3AINTENSITYMATCHREFERENCE+AND+%0AMS1MZ%3DX%2B2%3ATOLERANCEMZ%3D0.1%3AINTENSITYMATCH%3DY%2A0.66%3AINTENSITYMATCHPERCENT%3D30+AND+%0AMS1MZ%3DX-2%3ATOLERANCEMZ%3D0.1%3AINTENSITYMATCH%3DY%2A0.66%3AINTENSITYMATCHPERCENT%3D30+AND+MS1MZ%3DX%2B4%3ATOLERANCEMZ%3D0.2%3AINTENSITYMATCH%3DY%2A0.17%3AINTENSITYMATCHPERCENT%3D40+AND+%0AMS1MZ%3DX-4%3ATOLERANCEMZ%3D0.2%3AINTENSITYMATCH%3DY%2A0.17%3AINTENSITYMATCHPERCENT%3D40+AND+%0AMS2PREC%3DX&filename=GNPS00002_A3_p.mzML&x_axis=&y_axis=&facet_column=&scan=&x_value=572.828&y_value=0.64&ms1_usi=mzspec%3AGNPS%3ATASK-f6e8346934904399ae6742723762b2cb-f.MSV000084691%2Fccms_peak%2F1810E-II.mzML%3Ascan%3A474&ms2_usi=)

Visualization image of MS2 spectra

```/visualize/ms2```

## License

MIT License
