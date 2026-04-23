#!/usr/bin/env python3
"""Generate per-(file, query) engine reference JSONs.

Each JSON captures just enough of the Python `msql_engine.process_query`
output to let the Rust engine prove correctness without having to
reproduce pandas' exact text formatting:

* `row_count` — number of output rows (= scans for scaninfo queries)
* `scans` — full sorted scan list
* `per_scan` — for scaninfo queries, the full aggregated row keyed
  by scan (rt, i_sum, i_norm_max, and optionally precmz/ms1scan/charge)

Usage: run with no args — it iterates a hard-coded fixture list so
adding a new Rust test case is a one-line change to `FIXTURES`.
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd

from massql import msql_engine


HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

FIXTURES = [
    # --- scaninfo + single-condition core cases ---
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEMZ=0.1",
     "a3p_ms2prod_226"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEPPM=5",
     "a3p_ms2prod_226_ppm"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS1DATA) WHERE POLARITY=Positive",
     "a3p_polarity_positive"),
    ("tests/data/GNPS00002_A10_n.mzML",
     "QUERY scaninfo(MS1DATA) WHERE POLARITY=Negative",
     "a10n_polarity_negative"),

    # --- multi-condition AND, NL, different query functions ---
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=86.09643:TOLERANCEMZ=0.01 AND MS2PROD=104.1075:TOLERANCEMZ=0.01",
     "a3p_ms2prod_and"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2NL=18.0:TOLERANCEMZ=0.05",
     "a3p_ms2nl_18"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scansum(MS1DATA) WHERE MS1MZ=100:TOLERANCEMZ=0.1",
     "a3p_scansum_ms1_100"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scannum(MS2DATA) WHERE MS2PREC=226.18:TOLERANCEMZ=0.5",
     "a3p_scannum_prec226"),

    # --- scan / rt / charge / intensity qualifiers ---
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS1DATA) WHERE SCANMIN=20 AND SCANMAX=30",
     "a3p_scan_range"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS1DATA) WHERE RTMIN=0.1 AND RTMAX=0.2",
     "a3p_rt_range"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE CHARGE=1",
     "a3p_charge1"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=86.09643:TOLERANCEMZ=0.01:INTENSITYPERCENT>10",
     "a3p_intensity_percent"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=86.09643:TOLERANCEMZ=0.01:INTENSITYTICPERCENT>5",
     "a3p_intensity_tic_percent"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=86.09643:TOLERANCEMZ=0.01:INTENSITYVALUE>500",
     "a3p_intensity_value"),

    # --- EXCLUDED (negation), formula literal ---
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEPPM=5:EXCLUDED",
     "a3p_excluded"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=formula(C10)",
     "a3p_formula_c10"),

    # --- FILTER clause (narrow peaks within matching scans) ---
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scansum(MS1DATA) WHERE MS1MZ=100:TOLERANCEMZ=0.5 FILTER MS1MZ=100:TOLERANCEMZ=0.1",
     "a3p_filter_ms1"),

    # --- INTENSITYMATCH isotope-ratio query ---
    ("tests/data/JB_182_2_fe.mzML",
     "QUERY scaninfo(MS1DATA) WHERE RTMIN=3.03 AND RTMAX=3.05 AND MS1MZ=X-2:INTENSITYMATCH=Y*0.063:INTENSITYMATCHPERCENT=25 AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE FILTER MS1MZ=X",
     "jb_iron_isotope"),

    # INTENSITYMATCH with Y*f(X) qualifier expression — combines X
    # substitution + register read.
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS1MZ=X-2:INTENSITYMATCH=Y*(0.0608+(.000002*X)):INTENSITYMATCHPERCENT=25 AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE:INTENSITYPERCENT=5 AND MS2PREC=X",
     "a3p_intensitymatch_yfx"),

    # --- Variable queries ---
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=2.0*(X - formula(Fe))",
     "a3p_var_prod_fe"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X :TOLERANCEMZ=0.1:INTENSITYPERCENT=5 AND MS2PROD=X+119.1 :TOLERANCEMZ=0.1:INTENSITYPERCENT=5",
     "a3p_var_prod_119"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS1DATA) WHERE MS1MZ=(X OR X+2 OR X+4 OR X+6)",
     "a3p_var_ms1_or"),

    # --- OR-list values, MASSDEFECT qualifier, FILTER + MASSDEFECT combo ---
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=(86.09643 OR 104.1075):TOLERANCEMZ=0.01",
     "a3p_or_list"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=100:TOLERANCEMZ=100:MASSDEFECT=massdefect(min=0.05, max=0.15)",
     "a3p_massdefect"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scansum(MS1DATA) FILTER MS1MZ=515:TOLERANCEMZ=35:MASSDEFECT=massdefect(min=0.1332, max=0.2112)",
     "a3p_filter_massdefect"),
]


def _ref_row(row: pd.Series, has_ms2: bool):
    out = {
        "scan": int(row["scan"]),
        "rt": float(row["rt"]),
        "i_sum": float(row["i"]),
        "i_norm_max": float(row["i_norm"]),
    }
    if has_ms2:
        out["precmz"] = float(row["precmz"])
        out["ms1scan"] = int(row["ms1scan"])
        out["charge"] = int(row["charge"])
    # Variable-pipeline X candidate (absent for non-variable queries).
    if "comment" in row.index and pd.notna(row["comment"]):
        try:
            out["comment"] = float(row["comment"])
        except (ValueError, TypeError):
            pass
    return out


def dump(mzml_rel: str, query: str, name: str):
    abspath = REPO / mzml_rel
    df = msql_engine.process_query(query, str(abspath))

    ref = {
        "file": mzml_rel,
        "query": query,
        "row_count": int(len(df)),
        "scans": sorted(int(s) for s in df.get("scan", pd.Series([], dtype=int))),
    }

    is_scaninfo = "scaninfo" in query
    if is_scaninfo and len(df):
        has_ms2 = "precmz" in df.columns
        per_scan = [_ref_row(df.iloc[i], has_ms2) for i in range(len(df))]
        per_scan.sort(key=lambda r: r["scan"])
        ref["per_scan"] = per_scan
    else:
        ref["per_scan"] = []

    out_path = HERE / "engine" / f"{name}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(ref, f, indent=2)
    print(f"  wrote {out_path.relative_to(REPO)}  ({ref['row_count']} rows)")


def main():
    os.chdir(REPO)
    for mzml, query, name in FIXTURES:
        print(f"[{name}] {mzml}  :: {query}")
        dump(mzml, query, name)


if __name__ == "__main__":
    sys.exit(main())
