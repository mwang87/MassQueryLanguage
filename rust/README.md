# MassQL — Rust port

A Rust re-implementation of the MassQL reference engine that lives in
[`../massql/`](../massql). The aim is a drop-in replacement for the
Python CLI on the core (non-variable) query shapes, with byte-identical
parser JSON and close-enough engine output (numeric-tolerance parity).

## Layout

```
rust/
├── massql-parser/      grammar + parse tree → JSON (matches msql_parser.py)
├── massql-loader/      mzML / mzXML / MGF / GNPS JSON → ms1/ms2 peak tables,
│                       plus scan-extract helpers + MGF / mzML writers
├── massql-engine/      condition execution + scaninfo / scansum / scannum / scanmz
├── massql-translator/  parsed-query → plain-English explanation
├── massql-cli/         `massql` binary — drop-in for `python -m massql.msql_cmd`
└── references/         fixture generators + sweep harness (Python helpers)
```

Each crate is independently testable. `massql-parser` has no mass-spec
dependencies; `massql-loader` pulls in [`mzdata`](https://crates.io/crates/mzdata)
for file parsing; `massql-engine` adds conditions and collation;
`massql-cli` ties them together behind a `clap`-parsed binary.

## What works today

| Pipeline stage     | Rust status                                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------------------------ |
| Parser             | **Complete parity** — all 47 `tests/reference_parses/*.json` match Python byte-for-byte                      |
| Loader (mzML)      | **Row-count + sample parity** against Python on 45 k – 2.4 M row files                                       |
| Loader (MGF)       | Parity modulo the one-row MS1 sentinel Python stuffs in for DataFrame safety (we drop it)                    |
| Loader (mzXML)     | Custom XML + base64 reader (quick-xml + base64 + flate2). 2.4 M peak file matches Python exactly.            |
| Loader (GNPS JSON) | Row counts match; the Python loader stores the string `spectrum_id` as each peak's `scan`, whereas Rust uses sequential u32 scan numbers (documented divergence). |
| Engine: WHERE      | MS2PROD, MS2PREC, MS2NL, MS1MZ, RTMIN/MAX, SCANMIN/MAX, POLARITY, CHARGE, MOBILITY range                     |
| Engine: qualifiers | TOLERANCEMZ, TOLERANCEPPM, INTENSITYVALUE/PERCENT/TICPERCENT (all comparators), EXCLUDED, MASSDEFECT, CARDINALITY / MATCHCOUNT |
| Engine: FILTER     | MS1MZ and MS2PROD (including MASSDEFECT)                                                                     |
| Query functions    | bare `MS1DATA`/`MS2DATA`, `scaninfo`, `scansum`, `scannum`, `scanmz`                                         |
| CLI                | TSV / CSV output, alphabetically sorted columns, integer typing, Python-compatible float formatting; `comment` + `mz_lower/mz_upper` when an X variable produced the row |
| CLI: `--extract-json` | Re-reads the input file and writes one JSON object per matched spectrum (`{peaks, mslevel, scan, precursor_mz, new_scan, query_results}`), mirroring Python's `--extract_json`. mzML + MGF. |
| CLI: `--extract-mgf` / `--extract-mzml` | Writes matched spectra as MGF (text) or mzML (via `mzdata::io::MzMLWriter`). Roundtrips — the extracted file loads back through the same reader. |
| CLI: `--translate`   | Prints a plain-English description of the query. Wraps [`massql_translator::translate_query`]; matches Python's `msql_translator` phrasing for the subset we've ported. |
| **X variables**    | `MS2PROD=X`, `MS2PREC=X`, `MS1MZ=X`, `MS2NL=X`, `X=range(...)`, `X=massdefect(...)`, expression substitution (`X-2`, `2.0*(X-formula(Fe))`, `X*0.0006775+0.40557`), mobility ranges with X |
| **INTENSITYMATCH** | Per-scan intensity register backing `INTENSITYMATCHREFERENCE` ↔ `INTENSITYMATCH=Y*k:INTENSITYMATCHPERCENT=…` pairs. Isotope-ratio queries match Python exactly. |

### Not ported (yet)

These return a deliberate `semantic` error from the engine so diffs
against Python surface the gap rather than producing silent zeros:

* **OTHERSCAN** — not present in any existing test.
* **Nested subqueries** (`condition = (statement)`).
* **`peptide(...)`** expression — grammar accepts it; engine errors out
  until we wire up a pyteomics-equivalent residue mass computation.

## Test commands

```sh
cd rust

# Full suite — 33 tests covering all layers:
#   - parser unit tests + 47-fixture sweep against Python reference JSONs
#   - loader parity on 6 mzML files (30k–3M peaks) + 1 MGF file
#   - 20 engine parity tests (WHERE, FILTER, OR-lists, MASSDEFECT,
#     INTENSITY*, EXCLUDED, CARDINALITY, MOBILITY, scan/rt ranges)
cargo test

# CLI parity vs live Python (spawns `python3 -m massql.msql_cmd` per
# case, compares TSV output with 0.5% numeric tolerance):
PYTHON_PARITY=1 cargo test -p massql-cli --test cli_vs_python

# Broad sweep over every query in tests/test_queries.txt. Each query
# runs through both CLIs and outputs are row-diffed. Latest result:
#   match         49   - byte-exact TSV agreement within tolerance
#   rust_error     0
# => Every query shape in test_queries.txt matches the Python CLI.
python3 references/broad_cli_sweep.py

# Quick wall-clock benchmark (release build):
bash references/benchmark.sh
# Typical:  Python  ~2.6s  |  Rust  ~0.02s  (~130x on GNPS_A3_p.mzML)
```

## Regenerating fixtures

Three generator scripts live in `references/`:

```sh
# Loader reference (one JSON per mzML, with row counts + sampled rows):
python3 rust/references/dump_loader_reference.py tests/data/GNPS00002_A3_p.mzML \
    rust/references/loader/GNPS00002_A3_p.json

# Engine references (FIXTURES list at the top of the script):
python3 rust/references/dump_engine_reference.py

# CLI parity sweep (stdout only — no files written):
python3 rust/references/broad_cli_sweep.py
```

All three scripts must be run from the repo root so they can find
`tests/data/*.mzML`.

## Notes on behavioral differences

1. **Numeric precision**: the Rust engine sums intensities as `f64`,
   Python sums as `f32` (via pandas groupby on a `float32` column).
   Per-scan `i` columns therefore differ by ~1e-5 relative error;
   ship-readiness tests allow this tolerance.

2. **MS1 sentinel row**: the Python MGF loader stuffs a dummy MS1 row
   into `ms1_df` to avoid pandas errors on empty frames. The Rust
   loader returns an empty `ms1` vector instead. Any query relying on
   this row will diverge; none in the existing test suite do.

3. **`mz_defect` output column**: when a FILTER clause uses
   MASSDEFECT, pandas leaks an intermediate `mz_defect = mz - floor(mz)`
   column into the CSV output. The Rust engine mirrors this behavior
   so the TSV headers match exactly.
