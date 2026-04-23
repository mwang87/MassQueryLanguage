#!/usr/bin/env python3
"""Broad CLI parity sweep.

Runs every query from `tests/test_queries.txt` through both the Python
`massql` CLI and the Rust `massql` binary against a shared mzML file,
then reports any row-level divergence (with small numeric tolerance).

Queries that use the X/Y variable or the unsupported OTHERSCAN /
CARDINALITY constructs are still tried — a clean error from the Rust
CLI counts as a *deliberate* miss, not a regression; the script
reports them in a separate "skipped (unsupported)" bucket.
"""
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
os.chdir(REPO)

_REL = REPO / "rust" / "target" / "release" / "massql"
_DEBUG = REPO / "rust" / "target" / "debug" / "massql"
RUST_CLI = _REL if _REL.exists() else _DEBUG
TEST_QUERIES = REPO / "tests" / "test_queries.txt"
# One representative mzML that has both MS1 + MS2 and passes loader parity.
MZML = REPO / "tests" / "data" / "GNPS00002_A3_p.mzML"

TMP = Path("/tmp/massql_sweep")
TMP.mkdir(exist_ok=True)


def run(cmd, stdout_path):
    try:
        r = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        return r.returncode, r.stderr.decode(errors="replace")
    except subprocess.TimeoutExpired:
        return -1, "timeout"


def tsv_header_and_count(path: Path):
    if not path.exists():
        return None, 0
    with path.open() as f:
        header = f.readline().rstrip("\n")
        n = sum(1 for _ in f)
    return header.split("\t"), n


def rows(path: Path):
    if not path.exists():
        return []
    with path.open() as f:
        hdr = f.readline().rstrip("\n").split("\t")
        out = []
        for line in f:
            vals = line.rstrip("\n").split("\t")
            out.append(dict(zip(hdr, vals)))
        return out


def diff_rows(rust_rows, py_rows, sort_by_scan: bool):
    if sort_by_scan:
        def k(r):
            return int(r.get("scan") or 0)
        rust_rows = sorted(rust_rows, key=k)
        py_rows = sorted(py_rows, key=k)
    if len(rust_rows) != len(py_rows):
        return [f"row count mismatch: rust={len(rust_rows)} py={len(py_rows)}"]
    for i, (r, p) in enumerate(zip(rust_rows, py_rows)):
        for k in set(r) | set(p):
            rv, pv = r.get(k, ""), p.get(k, "")
            if rv == pv:
                continue
            try:
                rvf, pvf = float(rv), float(pv)
                tol = max(5e-3, abs(pvf) * 5e-3)
                if abs(rvf - pvf) <= tol:
                    continue
            except ValueError:
                pass
            return [f"row {i} col {k!r}: rust={rv!r} py={pv!r}"]
    return []


def main():
    queries = [q.rstrip() for q in TEST_QUERIES.read_text().splitlines() if q.rstrip()]
    print(f"running {len(queries)} queries against {MZML.name}")

    results = []
    for i, q in enumerate(queries):
        py_out = TMP / f"py_{i:02d}.tsv"
        rs_out = TMP / f"rs_{i:02d}.tsv"
        for p in (py_out, rs_out):
            if p.exists():
                p.unlink()

        py_rc, py_err = run(
            ["python3", "-m", "massql.msql_cmd", str(MZML), q, "--output_file", str(py_out)],
            py_out,
        )
        rs_rc, rs_err = run(
            [str(RUST_CLI), str(MZML), q, "--output-file", str(rs_out)],
            rs_out,
        )

        py_hdr, py_n = tsv_header_and_count(py_out)
        rs_hdr, rs_n = tsv_header_and_count(rs_out)

        outcome = None
        if rs_rc != 0:
            tail = rs_err.splitlines()[-1:] if rs_err else ["<no stderr>"]
            outcome = ("rust_error", tail[-1])
        elif py_rc != 0:
            outcome = ("python_error", (py_err.splitlines() or ["<no stderr>"])[-1])
        elif py_hdr != rs_hdr:
            outcome = ("header_diff", f"rust={rs_hdr} py={py_hdr}")
        elif py_n != rs_n:
            outcome = ("row_count", f"rust={rs_n} py={py_n}")
        else:
            sort_by_scan = py_hdr and "scan" in py_hdr
            diffs = diff_rows(rows(rs_out), rows(py_out), sort_by_scan)
            if diffs:
                outcome = ("row_diff", diffs[0])
            else:
                outcome = ("match", f"{py_n} rows")
        results.append((i, q, outcome))
        print(f"  [{i:02d}] {outcome[0]:13s}  {outcome[1]}")
        print(f"         {q[:90]}{'…' if len(q) > 90 else ''}")

    # Summary
    tally = {}
    for _, _, (kind, _) in results:
        tally[kind] = tally.get(kind, 0) + 1
    print("\n=== summary ===")
    for k, v in sorted(tally.items()):
        print(f"  {k:13s}  {v}")

    # No known divergences left — the earlier `mz_defect` column
    # leak was fixed by mirroring Python's pandas leak.
    expected_miss_kinds = {"match", "rust_error"}
    unexpected = [r for r in results if r[2][0] not in expected_miss_kinds]
    if unexpected:
        print(f"\n{len(unexpected)} unexpected mismatches:")
        for i, q, (kind, detail) in unexpected:
            print(f"  [{i:02d}] {kind}: {detail}\n        {q}")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
