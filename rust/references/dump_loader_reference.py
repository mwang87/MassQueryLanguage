#!/usr/bin/env python3
"""Dump a per-file reference JSON from the Python massql loader so the
Rust loader has something to compare against.

Picks a deterministic sample of rows (strided) rather than dumping the
whole DataFrame — mismatches still surface because each sampled row
checks mz / i / scan / rt / polarity / (precmz, ms1scan, charge).

Usage:
    python dump_loader_reference.py <input.mzML> <output.json>

Run from anywhere; paths are resolved from CWD.
"""
import json
import sys
from pathlib import Path

import pandas as pd

from massql import msql_fileloading


def sample_rows(df: pd.DataFrame, max_samples: int = 30):
    if len(df) == 0:
        return [], 1
    stride = max(1, len(df) // max_samples)
    # Deterministic: first row, every `stride`-th, and the final row.
    indices = list(range(0, len(df), stride))
    if indices[-1] != len(df) - 1:
        indices.append(len(df) - 1)
    return indices, stride


def dump_ms1(df: pd.DataFrame):
    idxs, stride = sample_rows(df)
    out = []
    for i in idxs:
        row = df.iloc[i]
        out.append({
            "idx": int(i),
            "i": float(row["i"]),
            "mz": float(row["mz"]),
            "scan": int(row["scan"]),
            "rt": float(row["rt"]),
            "polarity": int(row["polarity"]),
        })
    return out, stride


def dump_ms2(df: pd.DataFrame):
    idxs, stride = sample_rows(df)
    out = []
    for i in idxs:
        row = df.iloc[i]
        out.append({
            "idx": int(i),
            "i": float(row["i"]),
            "mz": float(row["mz"]),
            "scan": int(row["scan"]),
            "rt": float(row["rt"]),
            "polarity": int(row["polarity"]),
            "precmz": float(row["precmz"]),
            "ms1scan": int(row["ms1scan"]),
            "charge": int(row["charge"]),
        })
    return out, stride


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    input_path = sys.argv[1]
    output_path = Path(sys.argv[2])

    ms1, ms2 = msql_fileloading.load_data(input_path)
    ms1_samples, ms1_stride = dump_ms1(ms1)
    ms2_samples, ms2_stride = dump_ms2(ms2)

    out = {
        "source_file": input_path,
        "ms1_count": int(len(ms1)),
        "ms2_count": int(len(ms2)),
        "sample_stride_ms1": ms1_stride,
        "sample_stride_ms2": ms2_stride,
        "ms1_samples": ms1_samples,
        "ms2_samples": ms2_samples,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"wrote {output_path} ({out['ms1_count']} MS1, {out['ms2_count']} MS2)")


if __name__ == "__main__":
    main()
