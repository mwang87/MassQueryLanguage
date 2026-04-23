//! File loading for the Rust massql port.
//!
//! Mirrors `massql/msql_fileloading.py::load_data` (default path
//! `_load_data_mzML_pyteomics`) — reads a mass-spec file and produces
//! two long-format peak tables (one row per peak, scan metadata
//! duplicated across peaks in the same scan).
//!
//! Only `.mzML` is implemented for now — other formats return a
//! descriptive error until we port them. The engine / CLI only needs
//! one path to be exercised end-to-end; adding mzXML / MGF / JSON / txt
//! is mechanical from here.

use std::path::Path;

use mzdata::io::{MGFReader, MzMLReader};
use mzdata::prelude::*;
use mzdata::spectrum::ScanPolarity;
use thiserror::Error;

pub mod extract;
pub mod mzxml;
pub use extract::{
    export_mgf, export_mzml, extract_mgf, extract_mzml, extract_scans, ExtractedSpectrum,
};
pub use mzxml::load_mzxml;

#[derive(Debug, Error)]
pub enum LoadError {
    #[error("unsupported file extension: {0}")]
    UnsupportedExtension(String),
    #[error("mzdata: {0}")]
    Mzdata(String),
    #[error("array retrieval: {0}")]
    ArrayRetrieval(#[from] mzdata::spectrum::bindata::ArrayRetrievalError),
    #[error("io: {0}")]
    Io(#[from] std::io::Error),
}

/// Encoded polarity, matching the Python reference's integer scheme:
/// 0 = unknown, 1 = positive, 2 = negative.
pub fn polarity_code(p: ScanPolarity) -> u8 {
    match p {
        ScanPolarity::Positive => 1,
        ScanPolarity::Negative => 2,
        ScanPolarity::Unknown => 0,
    }
}

/// A single MS1 peak, with scan metadata duplicated inline (long-format,
/// same as the Python `ms1_df`).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Ms1Peak {
    pub i: f32,
    pub i_norm: f32,
    pub i_tic_norm: f32,
    pub mz: f64,
    pub scan: u32,
    /// Retention time in minutes (matches the Python reference).
    pub rt: f64,
    pub polarity: u8,
}

/// A single MS2 (or higher) peak. The trailing fields (precmz, ms1scan,
/// charge, mobility) describe the selected precursor.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Ms2Peak {
    pub i: f32,
    pub i_norm: f32,
    pub i_tic_norm: f32,
    pub mz: f64,
    pub scan: u32,
    pub rt: f64,
    pub polarity: u8,
    pub precmz: f64,
    pub ms1scan: u32,
    pub charge: i32,
    pub mobility: Option<f64>,
}

/// Everything a query needs about a loaded file.
///
/// We keep MS1 and MS2 in separate vectors (matching the Python shape
/// of `ms1_df` / `ms2_df`) rather than a single tagged enum, because
/// every query touches exactly one of them per condition and the hot
/// path wants contiguous memory.
#[derive(Debug, Default, Clone)]
pub struct Dataset {
    pub ms1: Vec<Ms1Peak>,
    pub ms2: Vec<Ms2Peak>,
}

/// Dispatches on file extension.
pub fn load_file(path: impl AsRef<Path>) -> Result<Dataset, LoadError> {
    let path = path.as_ref();
    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_ascii_lowercase())
        .unwrap_or_default();

    match ext.as_str() {
        "mzml" => load_mzml(path),
        "mgf" => load_mgf(path),
        "mzxml" => load_mzxml(path),
        "json" => load_gnps_json(path),
        other => Err(LoadError::UnsupportedExtension(other.to_string())),
    }
}

/// Port of `_load_data_mzML_pyteomics`. Walks every spectrum once,
/// splits rows into the ms1/ms2 buckets, and keeps a running link
/// `previous_ms1_scan` so each MS2 peak carries the preceding MS1 scan.
pub fn load_mzml(path: impl AsRef<Path>) -> Result<Dataset, LoadError> {
    let mut reader = MzMLReader::open_path(path.as_ref()).map_err(|e| LoadError::Mzdata(e.to_string()))?;

    let mut ms1 = Vec::<Ms1Peak>::new();
    let mut ms2 = Vec::<Ms2Peak>::new();
    let mut previous_ms1_scan: u32 = 0;

    for spec in reader.iter() {
        let arrays = match spec.arrays.as_ref() {
            Some(a) => a,
            None => continue,
        };
        let intensities = arrays.intensities()?;
        if intensities.is_empty() {
            continue;
        }
        let mzs = arrays.mzs()?;

        let rt = spec.start_time();
        let scan = parse_scan_id(spec.id());
        let polarity = polarity_code(spec.polarity());
        let ms_level = spec.ms_level();

        // Scan-wide normalization factors (Python: i_max, i_sum).
        let i_max: f32 = intensities
            .iter()
            .copied()
            .fold(f32::MIN, f32::max)
            .max(f32::MIN_POSITIVE);
        let i_sum: f32 = intensities.iter().copied().sum::<f32>().max(f32::MIN_POSITIVE);

        if ms_level == 1 {
            ms1.reserve(intensities.len());
            for (&mz, &i) in mzs.iter().zip(intensities.iter()) {
                ms1.push(Ms1Peak {
                    i,
                    i_norm: i / i_max,
                    i_tic_norm: i / i_sum,
                    mz,
                    scan,
                    rt,
                    polarity,
                });
            }
            previous_ms1_scan = scan;
        } else if ms_level >= 2 {
            // Precursor m/z + charge + (optional) product-ion mobility.
            let (precmz, charge, mobility) = match spec.precursor() {
                Some(prec) => {
                    let ion = prec.ion();
                    let mz = ion.map(|i| i.mz).unwrap_or(0.0);
                    let charge = ion.and_then(|i| i.charge).unwrap_or(0);
                    // pyteomics reads "product ion mobility" off the
                    // selectedIon; mzdata surfaces ion mobility on the
                    // scan, which is equivalent for TIMS/IMS data.
                    let mobility = spec
                        .acquisition()
                        .scans
                        .first()
                        .and_then(|s| s.ion_mobility());
                    (mz, charge, mobility)
                }
                None => (0.0, 0, None),
            };

            ms2.reserve(intensities.len());
            for (&mz, &i) in mzs.iter().zip(intensities.iter()) {
                ms2.push(Ms2Peak {
                    i,
                    i_norm: i / i_max,
                    i_tic_norm: i / i_sum,
                    mz,
                    scan,
                    rt,
                    polarity,
                    precmz,
                    ms1scan: previous_ms1_scan,
                    charge,
                    mobility,
                });
            }
        }
        // Other ms_levels (0 = UV/VIS, etc.) are skipped — matches
        // Python's behavior of only branching on mslevel == 1 or 2.
    }

    Ok(Dataset { ms1, ms2 })
}

/// Port of `_load_data_gnps_json`. The file is a JSON array of
/// records, each carrying a `peaks_json` field that is itself a
/// JSON-encoded peak-list `[[mz, i], ...]`.
///
/// **Divergence from Python**: the Python loader stores each peak's
/// `scan` as the record's `spectrum_id` string (e.g.
/// `"CCMSLIB00000072227"`). Our `Ms2Peak::scan` is `u32`, so we
/// assign 1-based sequential scan numbers instead. Query results
/// therefore won't match on spectrum-id strings, but row counts and
/// all m/z / intensity semantics do.
pub fn load_gnps_json(path: impl AsRef<Path>) -> Result<Dataset, LoadError> {
    let raw = std::fs::read_to_string(path.as_ref())?;
    let records: Vec<serde_json::Value> =
        serde_json::from_str(&raw).map_err(|e| LoadError::Mzdata(e.to_string()))?;

    let mut ms2 = Vec::<Ms2Peak>::new();
    let mut scan_counter: u32 = 0;
    for spec in records {
        let peaks_json = match spec.get("peaks_json").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => continue,
        };
        // Python drops spectra whose peaks_json string exceeds 1 MB.
        if peaks_json.len() > 1_000_000 {
            continue;
        }
        let peaks: Vec<(f64, f64)> = match serde_json::from_str::<Vec<(f64, f64)>>(peaks_json) {
            Ok(p) => p.into_iter().filter(|(_, i)| *i > 0.0).collect(),
            Err(_) => continue,
        };
        if peaks.is_empty() {
            continue;
        }
        let i_max = peaks
            .iter()
            .map(|&(_, i)| i as f32)
            .fold(f32::MIN, f32::max)
            .max(f32::MIN_POSITIVE);
        let i_sum = peaks
            .iter()
            .map(|&(_, i)| i as f32)
            .sum::<f32>()
            .max(f32::MIN_POSITIVE);
        if i_max == 0.0 {
            continue;
        }
        let precmz = spec
            .get("Precursor_MZ")
            .and_then(|v| match v {
                serde_json::Value::Number(n) => n.as_f64(),
                serde_json::Value::String(s) => s.parse::<f64>().ok(),
                _ => None,
            })
            .unwrap_or(0.0);

        scan_counter = scan_counter.checked_add(1).unwrap_or(scan_counter);
        let scan = scan_counter;
        for &(mz, intensity) in &peaks {
            let i = intensity as f32;
            ms2.push(Ms2Peak {
                i,
                i_norm: i / i_max,
                i_tic_norm: i / i_sum,
                mz,
                scan,
                rt: 0.0,
                polarity: 1,
                precmz,
                ms1scan: 0,
                charge: 1,
                mobility: None,
            });
        }
    }

    Ok(Dataset { ms1: Vec::new(), ms2 })
}

/// Port of `_load_data_mgf_pyteomics`. MGF files are MS2-only in
/// practice; we populate `ms2` and leave `ms1` empty (the Python
/// reference stashes a single sentinel MS1 row — deliberately dropping
/// that since queries against an empty ms1_df behave identically).
///
/// Scan metadata comes from the spec's `params`:
///   * `SCANS` → scan number (fallback: 1-based index).
///   * `RTINSECONDS` → `start_time` in minutes (mzdata already converts).
///   * `PEPMASS` → precursor m/z (first entry).
///   * `CHARGE` → int after stripping trailing `+/-`.
pub fn load_mgf(path: impl AsRef<Path>) -> Result<Dataset, LoadError> {
    let mut reader = MGFReader::open_path(path.as_ref())
        .map_err(|e| LoadError::Mzdata(e.to_string()))?;

    let mut ms2 = Vec::<Ms2Peak>::new();

    let mut index: u32 = 0;
    while let Some(spec) = reader.read_next() {
        index += 1;

        let peaks = match spec.peaks.as_ref() {
            Some(p) if !p.is_empty() => p,
            _ => continue,
        };

        let scan = mgf_scan_from_params(&spec, index);
        let rt = spec.start_time();
        let (precmz, charge) = match spec.precursor() {
            Some(prec) => {
                let ion = prec.ion();
                (
                    ion.map(|i| i.mz).unwrap_or(0.0),
                    ion.and_then(|i| i.charge).unwrap_or(1),
                )
            }
            None => (0.0, 1),
        };

        let i_max: f32 = peaks
            .iter()
            .map(|p| p.intensity())
            .fold(f32::MIN, f32::max)
            .max(f32::MIN_POSITIVE);
        let i_sum: f32 = peaks.iter().map(|p| p.intensity()).sum::<f32>().max(f32::MIN_POSITIVE);

        ms2.reserve(peaks.len());
        for p in peaks.iter() {
            let i = p.intensity();
            if i == 0.0 {
                continue;
            }
            ms2.push(Ms2Peak {
                i,
                i_norm: i / i_max,
                i_tic_norm: i / i_sum,
                mz: p.mz(),
                scan,
                rt,
                // MGF is positive polarity by default in the Python
                // loader — there's no per-spectrum polarity field in
                // the format, so we mirror that choice.
                polarity: 1,
                precmz,
                ms1scan: 0,
                charge,
                mobility: None,
            });
        }
    }

    Ok(Dataset { ms1: Vec::new(), ms2 })
}

pub(crate) fn mgf_scan_from_params<C, D>(
    spec: &mzdata::spectrum::MultiLayerSpectrum<C, D>,
    fallback_index: u32,
) -> u32
where
    C: mzdata::prelude::CentroidLike + Default + Clone,
    D: mzdata::prelude::DeconvolutedCentroidLike + Default + Clone,
{
    for p in spec.description.params.iter() {
        if p.name.eq_ignore_ascii_case("scans") {
            // MGF SCANS is sometimes a range ("100-105"); Python takes
            // it verbatim. Keep it simple and parse the leading int.
            let s = p.value.to_string();
            let head: String = s.chars().take_while(|c| c.is_ascii_digit()).collect();
            if let Ok(n) = head.parse::<u32>() {
                return n;
            }
        }
    }
    fallback_index
}

/// Extract the numeric scan number from an mzML spectrum id.
///
/// Mirrors `int(spectrum["id"].replace("scanId=", "").split("scan=")[-1])`.
/// The defensive fallback returns 0 for an unparseable id rather than
/// panicking — pyteomics would raise, but in practice every modern mzML
/// produces one of the two id schemes this handles.
pub(crate) fn parse_scan_id(id: &str) -> u32 {
    let cleaned = id.replace("scanId=", "");
    let tail = cleaned.rsplit("scan=").next().unwrap_or("");
    tail.trim().parse::<u32>().unwrap_or_else(|_| {
        // Some producers just write a bare integer.
        cleaned.trim().parse::<u32>().unwrap_or(0)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_scan_id_handles_common_schemes() {
        assert_eq!(parse_scan_id("controllerType=0 controllerNumber=1 scan=42"), 42);
        assert_eq!(parse_scan_id("scanId=17"), 17);
        assert_eq!(parse_scan_id("scan=7"), 7);
        assert_eq!(parse_scan_id("scanId=0 scan=999"), 999);
    }
}
