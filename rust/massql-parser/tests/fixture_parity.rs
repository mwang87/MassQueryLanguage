//! Fixture-parity test: for every query in `tests/test_queries.txt`,
//! parse with the Rust implementation and compare the pretty-printed
//! JSON to the matching `tests/reference_parses/*.json` produced by
//! the Python reference parser.
//!
//! The file name is derived identically to the Python test:
//!   * `pathvalidate.sanitize_filename` on the query
//!   * replace " ", "=", "(", ")" with "_"
//!   * truncate to 50 chars
//!   * append `"___" + md5(query).hexdigest() + ".json"`

use std::fs;
use std::path::{Path, PathBuf};

use massql_parser::parse_msql;
use serde::Serialize;
use serde_json::ser::{PrettyFormatter, Serializer};

/// Match Python `json.dumps(obj, sort_keys=True, indent=4)`: 4-space
/// indent, with keys in sorted order (serde_json's default
/// `Map<String, Value>` is already sorted — it's a `BTreeMap` when the
/// `preserve_order` feature is off).
fn to_python_json(v: &serde_json::Value) -> String {
    let mut buf = Vec::new();
    let formatter = PrettyFormatter::with_indent(b"    ");
    let mut ser = Serializer::with_formatter(&mut buf, formatter);
    v.serialize(&mut ser).unwrap();
    String::from_utf8(buf).unwrap()
}

fn repo_root() -> PathBuf {
    // Crate is at <repo>/rust/massql-parser; walk up two levels.
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf()
    }

/// Python's `pathvalidate.sanitize_filename` strips `/`, `\`, `:`, `*`,
/// `?`, `"`, `<`, `>`, `|` plus control chars and a few NTFS-reserved
/// names. For our inputs only `:`, `<`, `>` matter.
fn sanitize_filename(s: &str) -> String {
    s.chars()
        .filter(|c| !matches!(c, '/' | '\\' | ':' | '*' | '?' | '"' | '<' | '>' | '|'))
        .filter(|c| !c.is_control())
        .collect()
}

fn fixture_filename(query: &str) -> String {
    let hash = format!("{:x}", md5::compute(query.as_bytes()));
    let mut base = sanitize_filename(query);
    base = base
        .replace(' ', "_")
        .replace('=', "_")
        .replace('(', "_")
        .replace(')', "_");
    if base.len() > 50 {
        base.truncate(50);
    }
    format!("{}___{}.json", base, hash)
}

#[test]
fn parses_match_python_reference() {
    let root = repo_root();
    let queries_path = root.join("tests/test_queries.txt");
    let reference_dir = root.join("tests/reference_parses");

    let queries = fs::read_to_string(&queries_path)
        .unwrap_or_else(|e| panic!("read {}: {}", queries_path.display(), e));

    let mut failures: Vec<String> = Vec::new();
    let mut count = 0;

    for line in queries.lines() {
        // Python: `line.rstrip()` — strip trailing whitespace incl. \r
        let query = line.trim_end();
        if query.is_empty() {
            continue;
        }
        count += 1;

        let parsed = match parse_msql(query) {
            Ok(v) => v,
            Err(e) => {
                failures.push(format!("PARSE ERROR [{}]: {}", query, e));
                continue;
            }
        };

        let got = to_python_json(&parsed);

        let filename = fixture_filename(query);
        let ref_path = reference_dir.join(&filename);
        let expected = match fs::read_to_string(&ref_path) {
            Ok(s) => s,
            Err(e) => {
                failures.push(format!(
                    "MISSING FIXTURE [{}]: {}\n  query: {}",
                    ref_path.display(),
                    e,
                    query
                ));
                continue;
            }
        };

        if got != expected {
            // First few diff lines help pinpoint the issue without
            // drowning stdout.
            let diff = simple_diff(&expected, &got);
            failures.push(format!(
                "MISMATCH {}\n  query: {}\n{}",
                filename, query, diff
            ));
        }
    }

    assert!(count > 0, "no queries found in {}", queries_path.display());

    if !failures.is_empty() {
        eprintln!(
            "\n{}/{} fixtures failed:\n",
            failures.len(),
            count
        );
        for f in &failures {
            eprintln!("{}\n", f);
        }
        panic!("{} fixture mismatches", failures.len());
    }
}

fn simple_diff(expected: &str, got: &str) -> String {
    let exp_lines: Vec<&str> = expected.lines().collect();
    let got_lines: Vec<&str> = got.lines().collect();
    let mut out = String::new();
    let max = exp_lines.len().max(got_lines.len());
    let mut shown = 0;
    for i in 0..max {
        let e = exp_lines.get(i).copied().unwrap_or("<missing>");
        let g = got_lines.get(i).copied().unwrap_or("<missing>");
        if e != g {
            out.push_str(&format!("  [{}] - {}\n", i, e));
            out.push_str(&format!("  [{}] + {}\n", i, g));
            shown += 1;
            if shown >= 8 {
                out.push_str("  ... (more diffs truncated)\n");
                break;
            }
        }
    }
    out
}
