

## What is Mass Query Language

The Mass Query Langauge is a domain specific language meant to be a succinct way to 
express a query in a mass spectrometry centric fashion. It is inspired by SQL, 
but it attempts to bake in assumptions of mass spectrometry to make querying much more
natural for mass spectrometry users. 

## Try it out

If you want to do a large scale query on your data, try our beta workflow [here](https://proteomics2.ucsd.edu/ProteoSAFe/index.jsp?params={%22workflow%22:%22MSQL%22,%22workflow_version%22:%22current%22}).

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

TOLERANCEMZ=0.1

TOLERANCEPPM=50

#### Intensity Relative to Full Spectrum

INTENSITYVALUE=1000

INTENSITYPERCENT>10

#### Intensity Relative to Other Peaks

INTENSITYMATCHREFERENCE

INTENSITYMATCH=Y

INTENSITYMATCH=Y*2

INTENSITYMATCHPERCENT=10

!!! info "Intensity Matching Between Peaks"
    This is actually complicated, but you'll end up with one peak per variable that is the reference
    and all others are relative to that reference. 
    ```
    WHERE 
    MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE 
    AND 
    MS1MZ=X+2:INTENSITYMATCH=Y*2:INTENSITYMATCHPERCENT=1 
    ```

## Examples

### XIC Generation

Precursor, m/z = 100

```
QUERY scansum(MS1DATA) WHERE MS1MZ=100:TOLERANCEMZ=0.1
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

