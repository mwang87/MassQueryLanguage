# MASS Query Languge

[![Unit Testing](https://github.com/mwang87/MassQueryLanguage/actions/workflows/test-unit.yml/badge.svg)](https://github.com/mwang87/MassQueryLanguage/actions/workflows/test-unit.yml)
[![NF Workflow Testing](https://github.com/mwang87/MassQueryLanguage/actions/workflows/test-workflow.yml/badge.svg)](https://github.com/mwang87/MassQueryLanguage/actions/workflows/test-workflow.yml)

This is the repository to define the language and reference implementation. This contains several parts

1. Language Grammar
1. Reference Implementation Python API
1. Commandline Utility to execute
1. NextFlow Workflow For Large Scale Analysis
1. ProteoSAFe workflow
1. Dash interactive exploration

## Developers/Contact

Mingxun Wang is the main creator and developer of MSQL. Contact me for contributing or using it!
## Docs

[Here](https://mwang87.github.io/MassQueryLanguage_Documentation/)


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

## Web API

```/api```
```/parse```


```/visualize/ms1```

[Example Link](/visualize/ms1?query=QUERY+scaninfo%28MS1DATA%29+WHERE+MS1MZ%3DX%3ATOLERANCEMZ%3D0.1%3AINTENSITYPERCENT%3D25%3AINTENSITYMATCH%3DY%3AINTENSITYMATCHREFERENCE+AND+%0AMS1MZ%3DX%2B2%3ATOLERANCEMZ%3D0.1%3AINTENSITYMATCH%3DY%2A0.66%3AINTENSITYMATCHPERCENT%3D30+AND+%0AMS1MZ%3DX-2%3ATOLERANCEMZ%3D0.1%3AINTENSITYMATCH%3DY%2A0.66%3AINTENSITYMATCHPERCENT%3D30+AND+MS1MZ%3DX%2B4%3ATOLERANCEMZ%3D0.2%3AINTENSITYMATCH%3DY%2A0.17%3AINTENSITYMATCHPERCENT%3D40+AND+%0AMS1MZ%3DX-4%3ATOLERANCEMZ%3D0.2%3AINTENSITYMATCH%3DY%2A0.17%3AINTENSITYMATCHPERCENT%3D40+AND+%0AMS2PREC%3DX&filename=GNPS00002_A3_p.mzML&x_axis=&y_axis=&facet_column=&scan=&x_value=572.828&y_value=0.64&ms1_usi=mzspec%3AGNPS%3ATASK-f6e8346934904399ae6742723762b2cb-f.MSV000084691%2Fccms_peak%2F1810E-II.mzML%3Ascan%3A474&ms2_usi=)

```/visualize/ms2```

## License

MIT License
