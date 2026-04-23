//! Re-read a mass-spec file and pull out the raw peaks for a set of
//! scan numbers. The shape matches `_extract_spectra` +
//! `_extract_mzML_scan` / `_extract_mgf_scan` in `msql_extract.py`.
//!
//! Unlike [`crate::load_mzml`], this doesn't normalize intensities
//! (it returns the raw peak arrays so downstream writers produce
//! byte-equivalent output). It also mirrors Python's quirk of
//! dropping peaks with `mz < 1` OR `intensity < 1`.

use std::collections::BTreeSet;
use std::io::{BufWriter, Write};
use std::path::Path;

use mzdata::io::{MGFReader, MzMLReader, MzMLWriter};
use mzdata::prelude::*;
use mzdata::spectrum::{
    ArrayType, BinaryArrayMap, BinaryDataArrayType, DataArray, MultiLayerSpectrum, Precursor,
    SelectedIon,
};

use crate::{parse_scan_id, LoadError};

/// Single extracted spectrum: raw peaks + a little metadata.
#[derive(Debug, Clone)]
pub struct ExtractedSpectrum {
    /// Scan number parsed out of the spectrum id. Stringified to
    /// match Python's `str(spec.ID)` — preserves whatever numeric
    /// form the source file used.
    pub scan: String,
    pub mslevel: u8,
    /// `(mz, intensity)` pairs, sorted by mz ascending. Peaks with
    /// `mz < 1` or `intensity < 1` are dropped (Python does the
    /// same via `peaks[~np.any(peaks < 1.0, axis=1)]`).
    pub peaks: Vec<(f64, f32)>,
    /// Precursor m/z when the spectrum is MS2+. `None` for MS1.
    pub precursor_mz: Option<f64>,
}

/// Dispatch on file extension.
pub fn extract_scans(
    path: impl AsRef<Path>,
    scans: &BTreeSet<u32>,
) -> Result<Vec<ExtractedSpectrum>, LoadError> {
    let p = path.as_ref();
    let ext = p
        .extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_ascii_lowercase())
        .unwrap_or_default();

    match ext.as_str() {
        "mzml" => extract_mzml(p, scans),
        "mgf" => extract_mgf(p, scans),
        other => Err(LoadError::UnsupportedExtension(other.to_string())),
    }
}

pub fn extract_mzml(
    path: impl AsRef<Path>,
    scans: &BTreeSet<u32>,
) -> Result<Vec<ExtractedSpectrum>, LoadError> {
    let mut reader = MzMLReader::open_path(path.as_ref())
        .map_err(|e| LoadError::Mzdata(e.to_string()))?;

    let mut out = Vec::with_capacity(scans.len());
    for spec in reader.iter() {
        let scan_num = parse_scan_id(spec.id());
        if !scans.contains(&scan_num) {
            continue;
        }

        let Some(arrays) = spec.arrays.as_ref() else { continue };
        let intensities = arrays.intensities()?;
        if intensities.is_empty() {
            continue;
        }
        let mzs = arrays.mzs()?;

        // Python's `peaks[~np.any(peaks < 1.0, axis=1)]` then sort by
        // mz — we do both in one pass.
        let mut peaks: Vec<(f64, f32)> = mzs
            .iter()
            .zip(intensities.iter())
            .filter(|(&mz, &i)| mz >= 1.0 && i >= 1.0)
            .map(|(&mz, &i)| (mz, i))
            .collect();
        if peaks.is_empty() {
            continue;
        }
        peaks.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());

        let mslevel = spec.ms_level();
        let precursor_mz = if mslevel > 1 {
            spec.precursor().and_then(|p| p.ion().map(|i| i.mz))
        } else {
            None
        };

        out.push(ExtractedSpectrum {
            scan: scan_num.to_string(),
            mslevel,
            peaks,
            precursor_mz,
        });
    }
    Ok(out)
}

// ==================== Writers ====================
//
// Mirror of `_export_mgf` / `_export_mzML` in
// `massql/msql_extract.py`. Both take the already-extracted
// [`ExtractedSpectrum`] list; `new_scan` comes from the caller's
// enumeration index (1-based, matching Python's `current_scan`).

/// Write spectra as a `.mgf` file. One block per spectrum with the
/// `BEGIN IONS / PEPMASS / SCANS / <peaks> / END IONS` envelope that
/// Python produces. `new_scans` is parallel to `spectra`.
pub fn export_mgf(
    path: impl AsRef<Path>,
    spectra: &[ExtractedSpectrum],
    new_scans: &[u32],
) -> std::io::Result<()> {
    debug_assert_eq!(spectra.len(), new_scans.len());
    let f = std::fs::File::create(path.as_ref())?;
    let mut w = BufWriter::new(f);
    for (spec, &new_scan) in spectra.iter().zip(new_scans.iter()) {
        writeln!(w, "BEGIN IONS")?;
        if let Some(pm) = spec.precursor_mz {
            writeln!(w, "PEPMASS={}", pm)?;
        }
        writeln!(w, "SCANS={}", new_scan)?;
        for &(mz, intensity) in &spec.peaks {
            writeln!(w, "{} {}", mz, intensity)?;
        }
        writeln!(w, "END IONS")?;
    }
    w.flush()
}

/// Write spectra as an `.mzML` file via mzdata's writer. Each
/// spectrum gets id `scan=<new_scan>` and ms_level set; MS2+ spectra
/// include a precursor block. The resulting file loads back through
/// the same reader the loader uses.
pub fn export_mzml(
    path: impl AsRef<Path>,
    spectra: &[ExtractedSpectrum],
    new_scans: &[u32],
) -> std::io::Result<()> {
    debug_assert_eq!(spectra.len(), new_scans.len());
    let f = std::fs::File::create(path.as_ref())?;
    let mut writer: MzMLWriter<std::fs::File> = MzMLWriter::new(f);

    for (spec, &new_scan) in spectra.iter().zip(new_scans.iter()) {
        let mut out = MultiLayerSpectrum::default();
        out.description.id = format!("scan={}", new_scan);
        out.description.ms_level = spec.mslevel;

        let mut arrays = BinaryArrayMap::new();
        let mut mz_arr = DataArray::from_name_and_type(
            &ArrayType::MZArray,
            BinaryDataArrayType::Float64,
        );
        let mzs: Vec<f64> = spec.peaks.iter().map(|p| p.0).collect();
        let _ = mz_arr.extend(&mzs);
        let mut int_arr = DataArray::from_name_and_type(
            &ArrayType::IntensityArray,
            BinaryDataArrayType::Float32,
        );
        let ints: Vec<f32> = spec.peaks.iter().map(|p| p.1).collect();
        let _ = int_arr.extend(&ints);
        arrays.add(mz_arr);
        arrays.add(int_arr);
        out.arrays = Some(arrays);

        if let Some(pm) = spec.precursor_mz {
            let mut prec = Precursor::default();
            let mut ion = SelectedIon::default();
            ion.mz = pm;
            prec.add_ion(ion);
            out.description.precursor = vec![prec];
        }

        writer
            .write(&out)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))?;
    }
    writer
        .close()
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e.to_string()))?;
    Ok(())
}

pub fn extract_mgf(
    path: impl AsRef<Path>,
    scans: &BTreeSet<u32>,
) -> Result<Vec<ExtractedSpectrum>, LoadError> {
    let mut reader = MGFReader::open_path(path.as_ref())
        .map_err(|e| LoadError::Mzdata(e.to_string()))?;

    let mut out = Vec::with_capacity(scans.len());
    let mut index: u32 = 0;
    while let Some(spec) = reader.read_next() {
        index += 1;
        let scan_num = crate::mgf_scan_from_params(&spec, index);
        if !scans.contains(&scan_num) {
            continue;
        }
        let Some(spec_peaks) = spec.peaks.as_ref() else { continue };
        let mut peaks: Vec<(f64, f32)> = spec_peaks
            .iter()
            .map(|p| (p.mz(), p.intensity()))
            .filter(|&(mz, i)| mz >= 1.0 && i >= 1.0)
            .collect();
        if peaks.is_empty() {
            continue;
        }
        peaks.sort_by(|a, b| a.0.partial_cmp(&b.0).unwrap());

        let mslevel = spec.ms_level();
        let precursor_mz = if mslevel > 1 {
            spec.precursor().and_then(|p| p.ion().map(|i| i.mz))
        } else {
            None
        };

        out.push(ExtractedSpectrum {
            scan: scan_num.to_string(),
            mslevel,
            peaks,
            precursor_mz,
        });
    }
    Ok(out)
}
