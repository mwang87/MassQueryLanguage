

## What is Mass Spec Query Language

The Mass Spec Query Langauge (MSQL) is a domain specific language meant to be a succinct way to 
express a query in a mass spectrometry centric fashion. It is inspired by SQL, 
but it attempts to bake in assumptions of mass spectrometry to make querying much more
natural for mass spectrometry users. Broadly we attempt to design it according to several principles:

1. Expressiveness - Capture complex mass spectrometry patterns that the community would like to look for
1. Precision - Exactly prescribe how to find data without ambiguity
1. Relatively Natural - MSQL should be relatively easy to read and write and even use as a way to communicate ideas about mass spectrometry, you know like a language. 

## Try it out

If you want to do a large scale query on your data, try our beta workflow [here](https://proteomics2.ucsd.edu/ProteoSAFe/index.jsp?params=%7B%22workflow%22%3A%20%22MSQL-NF%22%7D).

## Definition of a Query

There are several parts

```
QUERY
<Type of Data>
WHERE
<Condition>
AND
<Condition>
FILTER
<Filter>
AND
<Filter>
```

### Type of Data

This determines the type of data you want to get. At its most fundamental level, its the peaks
for either 

1. MS1DATA
1. MS2DATA

Further, there are functions that can modify this data

1. scansum
1. scanrangesum
1. scanmaxint
1. scanmaxmz
1. scannum
1. scanrun
1. scaninfo

### Conditionals

These are conditions to filter for scans of interest (by looking for peaks and sets of peaks) within the mass spectrometry data. You can create clauses, 
which are specific conditions and the associated qualifiers. You may further combine multiple conditions with AND operators. 

The types of conditions are as follows

#### RTMIN

Setting the minimum retention time in minutes
#### RTMAX

Setting the maximum retention time in minutes

#### MS2PROD

Looking for an MS2 peak

#### MS2PREC

Looking for an MS2 precursor m/z

#### MS2NL

Looking for a neutral loss from precursor in the MS2 spectrum

### Qualifiers

These can be attached to conditions to modify some properties about the peaks we are looking for. 

#### Mass Accuracy

These two fields enable setting a peak m/z tolerance

```
TOLERANCEMZ=0.1
TOLERANCEPPM=50
```

#### Intensity Relative to Full Spectrum

These two fields enable to set an minimum intensity

```
INTENSITYVALUE=1000
INTENSITYPERCENT=10
```

#### Intensity Relative to Other Peaks

Here we can start imposing relative intensities between peaks

```
INTENSITYMATCHREFERENCE
INTENSITYMATCH=Y
INTENSITYMATCH=Y*2
INTENSITYMATCHPERCENT=10
```

!!! info "Intensity Matching Between Peaks"
    This is actually complicated, but you'll end up with one peak per variable that is the reference
    and all others are relative to that reference. 
    ```
    WHERE 
    MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE 
    AND 
    MS1MZ=X+2:INTENSITYMATCH=Y*2:INTENSITYMATCHPERCENT=1 
    ```


### Filters

Filters are like conditional but we don't elimate scans based on the condition. Rather, we simply filter out peaks within the spectra. 

This is useful for things like SRM or SIM/XIC. 


## Examples

### XIC Generation

MS1 XIC, m/z = 100

```
QUERY scansum(MS1DATA) FILTER MS1MZ=100:TOLERANCEMZ=0.1
```

### MS2 With Sugar Loss - Neutral Loss Scan

Neutral Loss, 163 Da

```
QUERY scannum(MS2DATA) WHERE MS2NL=163
```

### Brominated Compounds

```
QUERY scaninfo(MS2DATA) WHERE 
MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE 
AND MS1MZ=X+2:INTENSITYMATCH=Y:INTENSITYMATCHPERCENT=5
AND MS2PREC=X
```
### MS2 with distinct fragment(s) - Precursor Ion Scan

One Product Ion, m/z = 660.2
```
QUERY scaninfo(MS2DATA) WHERE MS2PROD=660.2:TOLERANCEMZ=0.1
```

Two Product Ions, m/z = 660.2 and 468.2
```
QUERY scaninfo(MS2DATA) WHERE MS2PROD=660.2:TOLERANCEMZ=0.1 AND MS2PROD=468.2:TOLERANCEMZ=0.1
```

## How To Use MSQL

### Python API

We have a python API that you can utilize in your own software

### Commandline Utility

We have a standalone script that can execute queries on single spectrum files. 

### Nextflow Workflow

We have a nextflow workflow to enable scalable queries across hundreds of thousands of mass spectrometry files

### ProteoSAFe Workflow

We have a proteosafe workflow that we have created that nicely integrates into GNPS. 

### Web API

We have built out a web API for people to use, especially for parsing. 

```
https://msql.ucsd.edu/parse?query=QUERY%20MS2DATA%20WHERE%20MS1MZ=100
```

Simply put in the query as a url encoded parameter and a JSON representation of the parse is returned. 