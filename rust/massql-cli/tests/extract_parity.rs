//! Parity test for `--extract-json` — spawn both CLIs and diff the
//! extracted-spectrum JSON output structurally.
//!
//! We don't diff the whole file byte-for-byte because numeric columns
//! (intensity sums in `query_results`, precursor m/z formatting) round
//! slightly differently between Rust's f64 summation and Python's
//! pandas f32 sum. Instead we check:
//!   * same number of JSON lines
//!   * each line has the same keys, in the same order
//!   * the `peaks` arrays are equal (raw peaks have no summation)
//!   * `scan` and `mslevel` match exactly
//!
//! Skipped unless `PYTHON_PARITY=1` is in the environment — same as
//! the base CLI parity test.

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

fn rust_cli() -> PathBuf {
    PathBuf::from(env!("CARGO_BIN_EXE_massql"))
}

fn python_available() -> bool {
    Command::new("python3")
        .args(["-c", "import massql.msql_cmd"])
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

fn parse_lines(path: &std::path::Path) -> Vec<serde_json::Value> {
    let text = match std::fs::read_to_string(path) {
        Ok(t) => t,
        Err(_) => return Vec::new(),
    };
    text.lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| serde_json::from_str(l).unwrap_or(serde_json::Value::Null))
        .collect()
}

fn run_case(mzml_rel: &str, query: &str) {
    let root = repo_root();
    let mzml = root.join(mzml_rel);

    let tag = format!("{:x}", md5sum(query.as_bytes()));
    let py_json = std::env::temp_dir().join(format!("massql_py_ex_{}.json", tag));
    let py_tsv = std::env::temp_dir().join(format!("massql_py_ex_{}.tsv", tag));
    let rs_json = std::env::temp_dir().join(format!("massql_rs_ex_{}.json", tag));
    let rs_tsv = std::env::temp_dir().join(format!("massql_rs_ex_{}.tsv", tag));
    for p in [&py_json, &py_tsv, &rs_json, &rs_tsv] {
        let _ = std::fs::remove_file(p);
    }

    let py = Command::new("python3")
        .arg("-m")
        .arg("massql.msql_cmd")
        .arg(&mzml)
        .arg(query)
        .arg("--output_file")
        .arg(&py_tsv)
        .arg("--extract_json")
        .arg(&py_json)
        .current_dir(&root)
        .output()
        .expect("spawn python");
    if !py.status.success() {
        panic!(
            "python failed on {}: {}",
            query,
            String::from_utf8_lossy(&py.stderr)
        );
    }

    let rs = Command::new(rust_cli())
        .arg(&mzml)
        .arg(query)
        .arg("--output-file")
        .arg(&rs_tsv)
        .arg("--extract-json")
        .arg(&rs_json)
        .current_dir(&root)
        .output()
        .expect("spawn rust");
    assert!(
        rs.status.success(),
        "rust failed: {}",
        String::from_utf8_lossy(&rs.stderr)
    );

    let py_lines = parse_lines(&py_json);
    let rs_lines = parse_lines(&rs_json);

    assert_eq!(
        py_lines.len(),
        rs_lines.len(),
        "spectrum-count mismatch for {}",
        query
    );

    // Match each pair by `scan` so row ordering doesn't matter.
    let by_scan_rs: HashMap<String, &serde_json::Value> = rs_lines
        .iter()
        .map(|s| (s["scan"].as_str().unwrap_or("").to_string(), s))
        .collect();

    for py_line in &py_lines {
        let scan = py_line["scan"].as_str().unwrap_or("").to_string();
        let rs_line = by_scan_rs
            .get(&scan)
            .unwrap_or_else(|| panic!("Rust missing extracted scan {}", scan));

        // Top-level key order.
        let py_keys: Vec<&String> = py_line.as_object().unwrap().keys().collect();
        let rs_keys: Vec<&String> = rs_line.as_object().unwrap().keys().collect();
        assert_eq!(py_keys, rs_keys, "top-level key order differs for scan {}", scan);

        // Peaks must be bit-identical — raw values, no summation.
        assert_eq!(py_line["peaks"], rs_line["peaks"], "peaks differ for scan {}", scan);

        // mslevel + precursor_mz must match exactly.
        assert_eq!(py_line["mslevel"], rs_line["mslevel"], "mslevel scan {}", scan);
        if let Some(py_pm) = py_line.get("precursor_mz") {
            let rs_pm = &rs_line["precursor_mz"];
            assert!(
                py_pm == rs_pm,
                "precursor_mz differs for scan {}: py={} rs={}",
                scan,
                py_pm,
                rs_pm
            );
        }

        // query_results key order.
        if let (Some(py_qr), Some(rs_qr)) = (
            py_line["query_results"].as_array(),
            rs_line["query_results"].as_array(),
        ) {
            assert_eq!(
                py_qr.len(),
                rs_qr.len(),
                "query_results count differs for scan {}",
                scan
            );
            if !py_qr.is_empty() {
                let py_qk: Vec<&String> = py_qr[0].as_object().unwrap().keys().collect();
                let rs_qk: Vec<&String> = rs_qr[0].as_object().unwrap().keys().collect();
                assert_eq!(py_qk, rs_qk, "query_results key order scan {}", scan);
            }
        }
    }
}

fn md5sum(bytes: &[u8]) -> u128 {
    let mut h: u128 = 0xcbf29ce484222325;
    for &b in bytes {
        h = h.wrapping_mul(0x100000001b3).wrapping_add(b as u128);
    }
    h
}

#[test]
fn extract_parity_vs_python() {
    if std::env::var("PYTHON_PARITY").ok().as_deref() != Some("1") {
        eprintln!("skipping: set PYTHON_PARITY=1 to run");
        return;
    }
    if !python_available() {
        panic!("PYTHON_PARITY=1 but python3/massql not available");
    }

    let cases: &[(&str, &str)] = &[
        ("tests/data/GNPS00002_A3_p.mzML",
         "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEMZ=0.1"),
        ("tests/data/GNPS00002_A3_p.mzML",
         "QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=2.0*(X - formula(Fe))"),
        ("tests/data/GNPS00002_A3_p.mzML",
         "QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEPPM=5:EXCLUDED"),
    ];

    for (mzml, query) in cases {
        eprintln!("[extract] {} :: {}", mzml, query);
        run_case(mzml, query);
    }
}
