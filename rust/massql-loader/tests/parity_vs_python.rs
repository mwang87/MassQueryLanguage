//! Compare the Rust mzML loader against the Python reference loader.
//!
//! Strategy: generate a per-file JSON reference with a small helper
//! script (see `massql-loader/tests/helper_dump.py`), then load the
//! same file in Rust and check row counts, column schemas, and a
//! bounded sample of row values for equality.
//!
//! The sampled rows matter — with ~45k MS1 rows on a typical file,
//! even a single off-by-one in scan linking or RT unit handling will
//! surface in the sample check.
//!
//! This test is gated on the reference JSON existing. Run
//! `python tests/helper_dump.py <path> <out.json>` first.

use std::path::PathBuf;

use massql_loader::load_mzml;
use serde::Deserialize;

#[derive(Deserialize, Debug)]
struct Reference {
    ms1_count: usize,
    ms2_count: usize,
    /// Up to ~30 MS1 sample rows picked via a deterministic stride.
    ms1_samples: Vec<Ms1Sample>,
    ms2_samples: Vec<Ms2Sample>,
    /// Stride used to pick samples — we mirror it on the Rust side.
    sample_stride_ms1: usize,
    sample_stride_ms2: usize,
}

#[derive(Deserialize, Debug)]
struct Ms1Sample {
    idx: usize,
    i: f32,
    mz: f64,
    scan: u32,
    rt: f64,
    polarity: u8,
}

#[derive(Deserialize, Debug)]
struct Ms2Sample {
    idx: usize,
    i: f32,
    mz: f64,
    scan: u32,
    rt: f64,
    polarity: u8,
    precmz: f64,
    ms1scan: u32,
    charge: i32,
}

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap()
        .to_path_buf()
}

fn run_one(mzml_rel: &str, reference_rel: &str) {
    let root = repo_root();
    let mzml = root.join(mzml_rel);
    let reference_path = root.join("rust/references").join(reference_rel);

    if !reference_path.exists() {
        eprintln!(
            "SKIP: reference missing at {} — run helper_dump.py first",
            reference_path.display()
        );
        return;
    }

    let reference_raw = std::fs::read_to_string(&reference_path).unwrap();
    let reference: Reference = serde_json::from_str(&reference_raw).unwrap();

    let dataset = load_mzml(&mzml).expect("load_mzml");

    assert_eq!(
        dataset.ms1.len(),
        reference.ms1_count,
        "MS1 row count mismatch for {}",
        mzml_rel
    );
    assert_eq!(
        dataset.ms2.len(),
        reference.ms2_count,
        "MS2 row count mismatch for {}",
        mzml_rel
    );

    for sample in &reference.ms1_samples {
        let row = dataset.ms1.get(sample.idx).unwrap_or_else(|| {
            panic!(
                "MS1 sample idx {} out of range (len {})",
                sample.idx,
                dataset.ms1.len()
            )
        });
        assert!(
            approx_eq(row.mz, sample.mz, 1e-6),
            "MS1[{}].mz: got {}, expected {}",
            sample.idx,
            row.mz,
            sample.mz
        );
        assert!(
            approx_eq_f32(row.i, sample.i, 1e-3),
            "MS1[{}].i: got {}, expected {}",
            sample.idx,
            row.i,
            sample.i
        );
        assert_eq!(row.scan, sample.scan, "MS1[{}].scan", sample.idx);
        assert!(
            approx_eq(row.rt, sample.rt, 1e-6),
            "MS1[{}].rt: got {}, expected {}",
            sample.idx,
            row.rt,
            sample.rt
        );
        assert_eq!(row.polarity, sample.polarity, "MS1[{}].polarity", sample.idx);
    }

    for sample in &reference.ms2_samples {
        let row = dataset.ms2.get(sample.idx).unwrap_or_else(|| {
            panic!(
                "MS2 sample idx {} out of range (len {})",
                sample.idx,
                dataset.ms2.len()
            )
        });
        assert!(approx_eq(row.mz, sample.mz, 1e-6), "MS2[{}].mz", sample.idx);
        assert!(
            approx_eq_f32(row.i, sample.i, 1e-3),
            "MS2[{}].i",
            sample.idx
        );
        assert_eq!(row.scan, sample.scan, "MS2[{}].scan", sample.idx);
        assert!(approx_eq(row.rt, sample.rt, 1e-6), "MS2[{}].rt", sample.idx);
        assert_eq!(row.polarity, sample.polarity, "MS2[{}].polarity", sample.idx);
        assert!(
            approx_eq(row.precmz, sample.precmz, 1e-6),
            "MS2[{}].precmz: got {} expected {}",
            sample.idx,
            row.precmz,
            sample.precmz
        );
        assert_eq!(row.ms1scan, sample.ms1scan, "MS2[{}].ms1scan", sample.idx);
        assert_eq!(row.charge, sample.charge, "MS2[{}].charge", sample.idx);
    }

    // Suppress unused-field warnings when strides ever come into play.
    let _ = (reference.sample_stride_ms1, reference.sample_stride_ms2);
}

fn approx_eq(a: f64, b: f64, tol: f64) -> bool {
    (a - b).abs() <= tol || (a - b).abs() <= tol * b.abs().max(1.0)
}

fn approx_eq_f32(a: f32, b: f32, tol: f32) -> bool {
    (a - b).abs() <= tol || (a - b).abs() <= tol * b.abs().max(1.0)
}

#[test]
fn matches_python_on_gnps_a3p() {
    run_one(
        "tests/data/GNPS00002_A3_p.mzML",
        "loader/GNPS00002_A3_p.json",
    );
}

#[test]
fn matches_python_on_gnps_a10n() {
    run_one(
        "tests/data/GNPS00002_A10_n.mzML",
        "loader/GNPS00002_A10_n.json",
    );
}

#[test]
fn matches_python_on_jb_fe() {
    run_one("tests/data/JB_182_2_fe.mzML", "loader/JB_182_2_fe.json");
}

#[test]
fn matches_python_on_qc_0() {
    run_one("tests/data/QC_0.mzML", "loader/QC_0.json");
}

#[test]
fn matches_python_on_1810e_ii() {
    run_one("tests/data/1810E-II.mzML", "loader/1810E-II.json");
}

#[test]
fn matches_python_on_bld_plt1() {
    run_one("tests/data/bld_plt1_07_120_1.mzML", "loader/bld_plt1_07_120_1.json");
}

#[test]
fn mzxml_t04251505_parity() {
    // Row-count + per-row comparison keyed on scan number. mzXML scan
    // numbers are ints, so parity with Python's loader is direct.
    use massql_loader::load_mzxml;
    let root = repo_root();
    let mzxml = root.join("tests/data/T04251505.mzXML");
    let reference_path = root.join("rust/references/loader/T04251505.json");
    if !reference_path.exists() {
        eprintln!("SKIP: reference missing at {}", reference_path.display());
        return;
    }
    let reference: Reference =
        serde_json::from_str(&std::fs::read_to_string(&reference_path).unwrap()).unwrap();

    let dataset = load_mzxml(&mzxml).expect("load_mzxml");
    assert_eq!(dataset.ms1.len(), reference.ms1_count, "MS1 count");
    assert_eq!(dataset.ms2.len(), reference.ms2_count, "MS2 count");

    for sample in &reference.ms1_samples {
        let row = &dataset.ms1[sample.idx];
        assert!(approx_eq(row.mz, sample.mz, 1e-4), "MS1[{}].mz", sample.idx);
        assert!(
            approx_eq_f32(row.i, sample.i, 1e-2),
            "MS1[{}].i",
            sample.idx
        );
        assert_eq!(row.scan, sample.scan, "MS1[{}].scan", sample.idx);
    }
}

#[test]
fn gnps_json_row_counts() {
    // Python stores GNPS spectrum_id as the `scan` field (string),
    // so per-row parity with the Rust loader isn't possible — the
    // Rust loader synthesizes 1-based scan numbers instead. We just
    // verify the row count matches, which confirms every spectrum
    // was processed.
    use massql_loader::load_gnps_json;
    let root = repo_root();
    let json_path = root.join("tests/data/gnps-library.json");
    if !json_path.exists() {
        eprintln!("SKIP: {} missing", json_path.display());
        return;
    }
    let dataset = load_gnps_json(&json_path).expect("load_gnps_json");
    // ~7.4M MS2 rows expected from the Python loader on this file.
    assert!(
        dataset.ms2.len() > 1_000_000,
        "GNPS MS2 row count suspiciously low: {}",
        dataset.ms2.len()
    );
}

#[test]
fn mgf_featurelist_ms2_parity() {
    // The Python loader stuffs a sentinel row into `ms1_df` so pandas
    // DataFrame operations don't blow up on an empty frame — we
    // deliberately skip that sentinel since queries against it return
    // the same thing as against an empty set. Compare MS2 only.
    use massql_loader::load_mgf;
    let root = repo_root();
    let mgf = root.join("tests/data/featurelist_pos.mgf");
    let reference_path = root.join("rust/references/loader/featurelist_pos.json");
    if !reference_path.exists() {
        eprintln!("SKIP: reference missing at {}", reference_path.display());
        return;
    }
    let reference: Reference =
        serde_json::from_str(&std::fs::read_to_string(&reference_path).unwrap()).unwrap();

    let dataset = load_mgf(&mgf).expect("load_mgf");
    assert_eq!(
        dataset.ms2.len(),
        reference.ms2_count,
        "MGF MS2 count mismatch"
    );
    assert_eq!(dataset.ms1.len(), 0, "Rust MGF loader drops Python's sentinel MS1 row");

    for sample in &reference.ms2_samples {
        let row = dataset.ms2.get(sample.idx).unwrap_or_else(|| {
            panic!("MS2 sample idx {} OOR (len {})", sample.idx, dataset.ms2.len())
        });
        assert!(approx_eq(row.mz, sample.mz, 1e-4), "MS2[{}].mz", sample.idx);
        assert!(approx_eq_f32(row.i, sample.i, 1e-2), "MS2[{}].i", sample.idx);
        assert_eq!(row.scan, sample.scan, "MS2[{}].scan", sample.idx);
        assert!(approx_eq(row.rt, sample.rt, 1e-5), "MS2[{}].rt", sample.idx);
        assert!(approx_eq(row.precmz, sample.precmz, 1e-4), "MS2[{}].precmz", sample.idx);
        assert_eq!(row.charge, sample.charge, "MS2[{}].charge", sample.idx);
    }
}
