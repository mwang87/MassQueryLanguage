#!/usr/bin/env python3
"""Time the Python CLI and the Rust CLI on the same queries.

Each row in the output table reports:
  * wall-clock seconds for Python (median of N runs, lower is better)
  * wall-clock seconds for Rust   (same)
  * speedup ratio (python / rust)
  * row count reported by each side (sanity check — they should agree
    modulo the known f32/f64 precision differences)

We intentionally use the Rust **release** binary and don't warm up
Python (cold start is what a user actually sees on a one-shot CLI
invocation). For long-running Python queries we drop to a single run.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
os.chdir(REPO)

RUST = REPO / "rust" / "target" / "release" / "massql"
assert RUST.exists(), f"release binary missing — `cargo build --release` first"

# (file, query, label, iterations)
CASES = [
    # --- small file, baseline load+query ---
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEPPM=5",
     "ms2prod ppm (small)", 3),

    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS1DATA) WHERE POLARITY=Positive",
     "scaninfo ms1 polarity (small)", 3),

    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE CHARGE=1",
     "ms2 charge (small)", 3),

    # --- medium file ---
    ("tests/data/JB_182_2_fe.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=100:TOLERANCEMZ=0.1",
     "ms2prod Da (32MB mzML)", 3),

    ("tests/data/QC_0.mzML",
     "QUERY scannum(MS2DATA) WHERE MS2PROD=156.01:TOLERANCEMZ=0.1",
     "scannum ms2 (49MB mzML)", 3),

    # --- large file ---
    ("tests/data/MMSRG_027.mzML",
     "QUERY scaninfo(MS1DATA) WHERE RTMIN=2 AND RTMAX=4",
     "rt window (158MB mzML)", 2),

    # --- variable queries (Python's slow path) ---
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=2.0*(X - formula(Fe))",
     "variable X+Fe (small)", 2),

    # --- INTENSITYMATCH isotope-ratio ---
    ("tests/data/JB_182_2_fe.mzML",
     "QUERY scaninfo(MS1DATA) WHERE RTMIN=3.03 AND RTMAX=3.05 AND MS1MZ=X-2:INTENSITYMATCH=Y*0.063:INTENSITYMATCHPERCENT=25 AND MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE FILTER MS1MZ=X",
     "iron isotope (INTENSITYMATCH)", 2),

    # --- MGF query ---
    ("tests/data/featurelist_pos.mgf",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=91.0546:TOLERANCEMZ=0.01",
     "mgf ms2prod", 3),
]


TIME_BIN = "/usr/bin/time"


def _time(cmd, cwd=REPO, timeout=600):
    start = time.perf_counter()
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=cwd,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, None
    elapsed = time.perf_counter() - start
    return elapsed, p.returncode


def _time_and_mem(cmd, cwd=REPO, timeout=600):
    """Returns `(elapsed_seconds, peak_rss_kb, returncode)`.

    Wraps the process in `/usr/bin/time -v` so we can read
    `Maximum resident set size` out of its stderr. Falls back to
    `_time` + `rss=None` if `/usr/bin/time` isn't available.
    """
    if not os.path.exists(TIME_BIN):
        t, rc = _time(cmd, cwd=cwd, timeout=timeout)
        return t, None, rc
    wrapped = [TIME_BIN, "-v"] + list(cmd)
    start = time.perf_counter()
    try:
        p = subprocess.run(
            wrapped,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            cwd=cwd,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, None, None
    elapsed = time.perf_counter() - start
    rss_kb = None
    for line in p.stderr.decode(errors="replace").splitlines():
        if "Maximum resident set size" in line:
            try:
                rss_kb = int(line.split(":")[-1].strip())
            except ValueError:
                pass
    return elapsed, rss_kb, p.returncode


def _rowcount(path):
    if not Path(path).exists():
        return 0
    with open(path) as f:
        # subtract header
        return max(0, sum(1 for _ in f) - 1)


def run_case(mzml, query, label, iterations, py_cache=False):
    """Time both CLIs. When `py_cache=True`, Python uses
    `--cache feather` with feathers pre-warmed — useful for showing
    Rust's default path against Python's best path.
    """
    py_out = Path("/tmp/bench_py.tsv")
    rs_out = Path("/tmp/bench_rs.tsv")

    py_cmd = ["python3", "-m", "massql.msql_cmd", mzml, query,
              "--output_file", str(py_out)]
    rs_cmd = [str(RUST), mzml, query, "--output-file", str(rs_out)]
    if py_cache:
        py_cmd += ["--cache", "feather"]
        _time(py_cmd)  # warm Python's feather

    py_times, rs_times, py_rss, rs_rss = [], [], [], []
    py_rc, rs_rc = 0, 0
    for i in range(iterations):
        for p in (py_out, rs_out):
            if p.exists():
                p.unlink()
        t, rss, rc = _time_and_mem(py_cmd)
        py_times.append(t if t is not None else float("inf"))
        if rss is not None:
            py_rss.append(rss)
        py_rc = rc or 0
        t, rss, rc = _time_and_mem(rs_cmd)
        rs_times.append(t if t is not None else float("inf"))
        if rss is not None:
            rs_rss.append(rss)
        rs_rc = rc or 0

    py_time = median(py_times)
    rs_time = median(rs_times)
    ratio = (py_time / rs_time) if (rs_time and rs_time > 0) else float("inf")
    return {
        "label": label,
        "py_time": py_time,
        "rs_time": rs_time,
        "ratio": ratio,
        "py_rows": _rowcount(py_out),
        "rs_rows": _rowcount(rs_out),
        "iterations": iterations,
        "py_rc": py_rc,
        "rs_rc": rs_rc,
        "py_cache": py_cache,
        "py_rss_mb": (max(py_rss) / 1024.0) if py_rss else None,
        "rs_rss_mb": (max(rs_rss) / 1024.0) if rs_rss else None,
    }


def main():
    # BENCH_PY_CACHE=1 → Python uses `--cache feather` with pre-warmed
    #                    feathers, showing Python's best path vs Rust.
    # default         → neither side caches.
    py_cache = os.environ.get("BENCH_PY_CACHE") == "1"
    if py_cache:
        banner = "mode: Python --cache feather (pre-warmed) vs Rust (no cache)"
    else:
        banner = "mode: no caching (every run parses the source file)"
    print(banner, file=sys.stderr)

    results = []
    for mzml, query, label, iters in CASES:
        if not Path(mzml).exists():
            print(f"SKIP ({mzml} missing): {label}", file=sys.stderr)
            continue
        print(f"running: {label} ({iters}× each side)", file=sys.stderr)
        r = run_case(mzml, query, label, iters, py_cache=py_cache)
        results.append(r)

    # Pretty table with time + peak RSS.
    print()
    header = "{:38s}  {:>9s}  {:>8s}  {:>8s}  {:>9s}  {:>8s}  {:>6s}".format(
        "query", "py_s", "rs_s", "speedup", "py_MB", "rs_MB", "mem×"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        py_mb = r["py_rss_mb"]
        rs_mb = r["rs_rss_mb"]
        mem_ratio = (py_mb / rs_mb) if (py_mb and rs_mb and rs_mb > 0) else None
        print("{:38s}  {:9.3f}  {:8.3f}  {:>7.1f}x  {:>9s}  {:>8s}  {:>6s}".format(
            r["label"][:38],
            r["py_time"],
            r["rs_time"],
            r["ratio"],
            f"{py_mb:.0f}" if py_mb is not None else "-",
            f"{rs_mb:.0f}" if rs_mb is not None else "-",
            f"{mem_ratio:.1f}x" if mem_ratio is not None else "-",
        ))
    print("-" * len(header))
    # Overall summary.
    finite = [r for r in results if r["ratio"] != float("inf")]
    if finite:
        geo = 1.0
        for r in finite:
            geo *= r["ratio"]
        geo = geo ** (1.0 / len(finite))
        total_py = sum(r["py_time"] for r in finite)
        total_rs = sum(r["rs_time"] for r in finite)
        print(f"\ngeometric mean speedup: {geo:.1f}x")
        print(f"total wall-clock:  python={total_py:.2f}s  rust={total_rs:.2f}s  ({total_py/total_rs:.1f}x)")


if __name__ == "__main__":
    main()
