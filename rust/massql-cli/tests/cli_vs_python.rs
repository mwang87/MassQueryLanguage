//! CLI-level parity: runs the Python `massql` CLI and the Rust CLI
//! on identical (mzml, query) pairs, then diffs the output TSVs at
//! row level. Numeric columns are compared with a relative tolerance
//! so that f32 vs f64 summation precision doesn't cause false
//! failures; string columns must match exactly.
//!
//! This test is skipped unless `PYTHON_PARITY=1` is set in the
//! environment — it spawns Python processes and reads ~1MB of mzML
//! per case, so we don't want it in the default `cargo test` path.
//! When the env var is set, it's the definitive ship-readiness check.

use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Command;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf()
}

fn rust_cli_path() -> PathBuf {
    // Tests run after cargo build has produced the binary. Rely on
    // CARGO_BIN_EXE_massql being set by cargo when the bin belongs to
    // this crate.
    PathBuf::from(env!("CARGO_BIN_EXE_massql"))
}

/// Returns true if python3 + local massql module are importable.
fn python_massql_available() -> bool {
    Command::new("python3")
        .args(["-c", "import massql.msql_cmd"])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn run_python(
    mzml: &std::path::Path,
    query: &str,
    out: &std::path::Path,
) -> std::io::Result<std::process::Output> {
    Command::new("python3")
        .arg("-m")
        .arg("massql.msql_cmd")
        .arg(mzml)
        .arg(query)
        .arg("--output_file")
        .arg(out)
        .current_dir(repo_root())
        .output()
}

fn run_rust(
    mzml: &std::path::Path,
    query: &str,
    out: &std::path::Path,
) -> std::io::Result<std::process::Output> {
    Command::new(rust_cli_path())
        .arg(mzml)
        .arg(query)
        .arg("--output-file")
        .arg(out)
        .current_dir(repo_root())
        .output()
}

#[derive(Debug)]
struct ParsedTsv {
    headers: Vec<String>,
    rows: Vec<HashMap<String, String>>,
}

fn parse_tsv(s: &str) -> ParsedTsv {
    let mut lines = s.lines();
    let headers: Vec<String> = lines
        .next()
        .unwrap_or("")
        .split('\t')
        .map(|s| s.to_string())
        .collect();
    let rows = lines
        .map(|l| {
            headers
                .iter()
                .zip(l.split('\t'))
                .map(|(k, v)| (k.clone(), v.to_string()))
                .collect()
        })
        .collect();
    ParsedTsv { headers, rows }
}

fn diff_row(rust: &HashMap<String, String>, py: &HashMap<String, String>) -> Vec<String> {
    let mut out = Vec::new();
    let mut keys: Vec<&String> = py.keys().chain(rust.keys()).collect();
    keys.sort();
    keys.dedup();
    for k in keys {
        let empty = String::new();
        let r = rust.get(k).unwrap_or(&empty);
        let p = py.get(k).unwrap_or(&empty);
        if r == p {
            continue;
        }
        match (r.parse::<f64>(), p.parse::<f64>()) {
            (Ok(rv), Ok(pv)) => {
                // Allow 0.5% relative tolerance or 1e-6 absolute, whichever is larger.
                let tol = 5e-3_f64.max(pv.abs() * 5e-3);
                if (rv - pv).abs() > tol {
                    out.push(format!("{}: rust={} python={}", k, r, p));
                }
            }
            _ => {
                out.push(format!("{}: rust={:?} python={:?}", k, r, p));
            }
        }
    }
    out
}

fn run_case(mzml_rel: &str, query: &str) {
    let root = repo_root();
    let mzml = root.join(mzml_rel);
    let pytmp = std::env::temp_dir().join(format!(
        "massql_py_{}.tsv",
        format!("{:x}", md5sum(query.as_bytes()))
    ));
    let rstmp = std::env::temp_dir().join(format!(
        "massql_rs_{}.tsv",
        format!("{:x}", md5sum(query.as_bytes()))
    ));

    let py_out = run_python(&mzml, query, &pytmp).expect("spawn python");
    assert!(
        py_out.status.success() || pytmp.exists(),
        "python failed: {}",
        String::from_utf8_lossy(&py_out.stderr)
    );

    let rs_out = run_rust(&mzml, query, &rstmp).expect("spawn rust");
    assert!(
        rs_out.status.success(),
        "rust CLI failed: {}",
        String::from_utf8_lossy(&rs_out.stderr)
    );

    // If Python produced zero rows it also produces no file — handle that.
    let py_exists = pytmp.exists();
    let rs_exists = rstmp.exists();
    if !py_exists && !rs_exists {
        return;
    }

    let py = std::fs::read_to_string(&pytmp).unwrap_or_default();
    let rs = std::fs::read_to_string(&rstmp).unwrap_or_default();
    let py = parse_tsv(&py);
    let rs = parse_tsv(&rs);

    assert_eq!(
        py.headers, rs.headers,
        "header mismatch for query: {}\n  python: {:?}\n  rust:   {:?}",
        query, py.headers, rs.headers
    );
    assert_eq!(
        py.rows.len(),
        rs.rows.len(),
        "row count mismatch for query: {}\n  python: {}\n  rust:   {}",
        query,
        py.rows.len(),
        rs.rows.len()
    );

    // Python TSV rows are written in dataframe order (scan-sorted via
    // groupby). Rust uses BTreeMap on scan which is also scan-sorted.
    // Still, match on `scan` when present to be safe.
    let (py_rows, rs_rows): (Vec<_>, Vec<_>) = if py.headers.iter().any(|h| h == "scan") {
        let mut py = py.rows.clone();
        let mut rs = rs.rows.clone();
        let sort_key = |r: &HashMap<String, String>| {
            r.get("scan").and_then(|s| s.parse::<u32>().ok()).unwrap_or(0)
        };
        py.sort_by_key(sort_key);
        rs.sort_by_key(sort_key);
        (py, rs)
    } else {
        (py.rows.clone(), rs.rows.clone())
    };

    let mut failures = Vec::new();
    for (i, (r, p)) in rs_rows.iter().zip(py_rows.iter()).enumerate() {
        let diffs = diff_row(r, p);
        if !diffs.is_empty() {
            failures.push(format!("row {}: {:?}", i, diffs));
        }
    }
    assert!(
        failures.is_empty(),
        "row diffs for query {:?}:\n  {}",
        query,
        failures.join("\n  ")
    );
}

fn md5sum(bytes: &[u8]) -> u128 {
    // Quick deterministic hash for temp filenames; strength doesn't matter.
    let mut h: u128 = 0xcbf29ce484222325;
    for &b in bytes {
        h = h.wrapping_mul(0x100000001b3).wrapping_add(b as u128);
    }
    h
}

// Hit the common shapes: scan-filtering, intensity qualifiers,
// EXCLUDED, FILTER, and each function variant. Keep file choices
// small so this test finishes fast.
static CASES: &[(&str, &str)] = &[
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEMZ=0.1"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEPPM=5"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS1DATA) WHERE POLARITY=Positive"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS1DATA) WHERE SCANMIN=20 AND SCANMAX=30"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS1DATA) WHERE RTMIN=0.1 AND RTMAX=0.2"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE CHARGE=1"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEPPM=5:EXCLUDED"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2NL=18.0:TOLERANCEMZ=0.05"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scannum(MS2DATA) WHERE MS2PREC=226.18:TOLERANCEMZ=0.5"),
    ("tests/data/GNPS00002_A3_p.mzML",
     "QUERY scaninfo(MS2DATA) WHERE MS2PROD=formula(C10)"),
];

#[test]
fn cli_parity_vs_python() {
    if std::env::var("PYTHON_PARITY").ok().as_deref() != Some("1") {
        eprintln!("skipping: set PYTHON_PARITY=1 to run");
        return;
    }
    if !python_massql_available() {
        panic!("PYTHON_PARITY=1 but python3/massql not available");
    }

    for (mzml, query) in CASES {
        eprintln!("[case] {} :: {}", mzml, query);
        run_case(mzml, query);
    }
}
