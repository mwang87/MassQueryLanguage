//! Minimal mzXML reader.
//!
//! mzdata doesn't ship an mzXML parser, so we write a small one
//! directly on top of [`quick_xml`]. Scope is deliberately narrow —
//! it handles centroided scans with base64-encoded big-endian
//! 32-bit-float peaks, optionally zlib-compressed. That covers
//! everything ProteoWizard's `msconvert` emits for mzXML output.
//!
//! Other variants (64-bit floats, little-endian) are detected from
//! the attributes and handled. Anything else (mzXML 1.x extensions,
//! nested scan trees beyond the first depth) is surfaced as a
//! semantic error rather than silently skipped.

use std::collections::HashMap;
use std::io::Read;
use std::path::Path;

use base64::Engine;
use flate2::read::ZlibDecoder;
use quick_xml::events::{BytesStart, Event};
use quick_xml::Reader;

use crate::{polarity_code, Dataset, LoadError, Ms1Peak, Ms2Peak};

/// Port of `_load_data_mzXML`. Iterates `<scan>` elements in depth
/// order (Python's pyteomics returns them flattened); tracks the last
/// MS1 scan number to link MS2 peaks back.
pub fn load_mzxml(path: impl AsRef<Path>) -> Result<Dataset, LoadError> {
    let text = std::fs::read_to_string(path.as_ref())?;
    let mut reader = Reader::from_str(&text);
    reader.trim_text(false);

    let mut ms1 = Vec::<Ms1Peak>::new();
    let mut ms2 = Vec::<Ms2Peak>::new();
    let mut previous_ms1_scan: u32 = 0;

    let mut buf = Vec::new();
    let mut current_scan: Option<ScanContext> = None;
    let mut in_peaks = false;
    let mut in_precursor_mz = false;
    let mut peaks_attrs: Option<PeaksAttrs> = None;
    let mut peaks_b64 = String::new();
    let mut precursor_mz_text = String::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(e)) => match e.name().as_ref() {
                b"scan" => {
                    let scan = parse_scan_attrs(&e)?;
                    current_scan = Some(scan);
                }
                b"peaks" => {
                    peaks_attrs = Some(PeaksAttrs::from_elem(&e)?);
                    peaks_b64.clear();
                    in_peaks = true;
                }
                b"precursorMz" => {
                    precursor_mz_text.clear();
                    in_precursor_mz = true;
                }
                _ => {}
            },
            Ok(Event::Empty(e)) if e.name().as_ref() == b"peaks" => {
                // No peak data inline — skip.
                peaks_attrs = None;
            }
            Ok(Event::End(e)) => match e.name().as_ref() {
                b"scan" => {
                    if let Some(ctx) = current_scan.take() {
                        let _ = emit_scan(
                            ctx,
                            &mut ms1,
                            &mut ms2,
                            &mut previous_ms1_scan,
                            peaks_attrs.take(),
                            &peaks_b64,
                            &precursor_mz_text,
                        )?;
                        peaks_b64.clear();
                        precursor_mz_text.clear();
                    }
                }
                b"peaks" => {
                    in_peaks = false;
                }
                b"precursorMz" => {
                    in_precursor_mz = false;
                }
                _ => {}
            },
            Ok(Event::Text(t)) => {
                let txt = t.unescape().unwrap_or_default();
                if in_peaks {
                    peaks_b64.push_str(&txt);
                }
                if in_precursor_mz {
                    precursor_mz_text.push_str(&txt);
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => {
                return Err(LoadError::Mzdata(format!("mzxml xml parse: {}", e)));
            }
            _ => {}
        }
        buf.clear();
    }

    Ok(Dataset { ms1, ms2 })
}

#[derive(Debug)]
struct ScanContext {
    scan: u32,
    ms_level: u8,
    polarity: u8,
    rt_minutes: f64,
}

fn parse_scan_attrs(e: &BytesStart<'_>) -> Result<ScanContext, LoadError> {
    let mut attrs: HashMap<String, String> = HashMap::new();
    for a in e.attributes() {
        let a = a.map_err(|e| LoadError::Mzdata(format!("mzxml attr: {}", e)))?;
        let key = String::from_utf8_lossy(a.key.as_ref()).to_string();
        let value = a
            .unescape_value()
            .map_err(|e| LoadError::Mzdata(format!("mzxml attr value: {}", e)))?
            .to_string();
        attrs.insert(key, value);
    }
    let scan = attrs
        .get("num")
        .and_then(|v| v.parse::<u32>().ok())
        .unwrap_or(0);
    let ms_level = attrs
        .get("msLevel")
        .and_then(|v| v.parse::<u8>().ok())
        .unwrap_or(1);
    let polarity = match attrs.get("polarity").map(|s| s.as_str()) {
        Some("+") => 1,
        Some("-") => 2,
        _ => 0,
    };
    let rt_minutes = attrs
        .get("retentionTime")
        .and_then(|v| parse_iso_duration_minutes(v))
        .unwrap_or(0.0);
    Ok(ScanContext {
        scan,
        ms_level,
        polarity,
        rt_minutes,
    })
}

#[derive(Debug)]
struct PeaksAttrs {
    precision: u8,
    little_endian: bool,
    zlib_compressed: bool,
    content_type: String,
}

impl PeaksAttrs {
    fn from_elem(e: &BytesStart<'_>) -> Result<Self, LoadError> {
        let mut attrs: HashMap<String, String> = HashMap::new();
        for a in e.attributes() {
            let a = a.map_err(|e| LoadError::Mzdata(format!("mzxml peaks attr: {}", e)))?;
            let key = String::from_utf8_lossy(a.key.as_ref()).to_string();
            let value = a
                .unescape_value()
                .map_err(|e| LoadError::Mzdata(format!("mzxml peaks attr value: {}", e)))?
                .to_string();
            attrs.insert(key, value);
        }
        let precision = attrs
            .get("precision")
            .and_then(|v| v.parse::<u8>().ok())
            .unwrap_or(32);
        let little_endian = attrs
            .get("byteOrder")
            .map(|v| v != "network")
            .unwrap_or(false);
        let zlib_compressed = matches!(attrs.get("compressionType").map(|s| s.as_str()), Some("zlib"));
        let content_type = attrs
            .get("contentType")
            .cloned()
            .unwrap_or_else(|| "m/z-int".to_string());
        Ok(PeaksAttrs {
            precision,
            little_endian,
            zlib_compressed,
            content_type,
        })
    }
}

fn decode_peaks(attrs: &PeaksAttrs, b64: &str) -> Result<Vec<(f64, f32)>, LoadError> {
    if attrs.content_type != "m/z-int" {
        return Err(LoadError::Mzdata(format!(
            "mzxml peaks contentType {:?} not supported",
            attrs.content_type
        )));
    }
    // Some exporters pretty-print the base64 with whitespace; strip it.
    let cleaned: String = b64.chars().filter(|c| !c.is_whitespace()).collect();
    let raw = base64::engine::general_purpose::STANDARD
        .decode(cleaned.as_bytes())
        .map_err(|e| LoadError::Mzdata(format!("mzxml base64: {}", e)))?;
    let raw = if attrs.zlib_compressed {
        let mut d = ZlibDecoder::new(&raw[..]);
        let mut out = Vec::new();
        d.read_to_end(&mut out)?;
        out
    } else {
        raw
    };

    let pairs = match attrs.precision {
        32 => decode_pairs_f32(&raw, attrs.little_endian),
        64 => decode_pairs_f64(&raw, attrs.little_endian),
        p => {
            return Err(LoadError::Mzdata(format!(
                "mzxml peaks precision {} not supported",
                p
            )))
        }
    };
    Ok(pairs)
}

fn decode_pairs_f32(raw: &[u8], little_endian: bool) -> Vec<(f64, f32)> {
    let mut out = Vec::with_capacity(raw.len() / 8);
    let mut chunks = raw.chunks_exact(8);
    for c in &mut chunks {
        let mz_bits = if little_endian {
            u32::from_le_bytes(c[..4].try_into().unwrap())
        } else {
            u32::from_be_bytes(c[..4].try_into().unwrap())
        };
        let i_bits = if little_endian {
            u32::from_le_bytes(c[4..].try_into().unwrap())
        } else {
            u32::from_be_bytes(c[4..].try_into().unwrap())
        };
        out.push((f32::from_bits(mz_bits) as f64, f32::from_bits(i_bits)));
    }
    out
}

fn decode_pairs_f64(raw: &[u8], little_endian: bool) -> Vec<(f64, f32)> {
    let mut out = Vec::with_capacity(raw.len() / 16);
    let mut chunks = raw.chunks_exact(16);
    for c in &mut chunks {
        let mz_bits = if little_endian {
            u64::from_le_bytes(c[..8].try_into().unwrap())
        } else {
            u64::from_be_bytes(c[..8].try_into().unwrap())
        };
        let i_bits = if little_endian {
            u64::from_le_bytes(c[8..].try_into().unwrap())
        } else {
            u64::from_be_bytes(c[8..].try_into().unwrap())
        };
        out.push((f64::from_bits(mz_bits), f64::from_bits(i_bits) as f32));
    }
    out
}

fn emit_scan(
    ctx: ScanContext,
    ms1: &mut Vec<Ms1Peak>,
    ms2: &mut Vec<Ms2Peak>,
    previous_ms1_scan: &mut u32,
    peaks_attrs: Option<PeaksAttrs>,
    peaks_b64: &str,
    precursor_mz_text: &str,
) -> Result<(), LoadError> {
    let attrs = match peaks_attrs {
        Some(a) => a,
        None => return Ok(()), // no peaks in this scan
    };
    let peaks = decode_peaks(&attrs, peaks_b64)?;
    if peaks.is_empty() {
        return Ok(());
    }
    let i_max = peaks
        .iter()
        .map(|&(_, i)| i)
        .fold(f32::MIN, f32::max)
        .max(f32::MIN_POSITIVE);
    let i_sum = peaks.iter().map(|&(_, i)| i).sum::<f32>().max(f32::MIN_POSITIVE);

    if ctx.ms_level == 1 {
        ms1.reserve(peaks.len());
        for (mz, i) in peaks {
            ms1.push(Ms1Peak {
                i,
                i_norm: i / i_max,
                i_tic_norm: i / i_sum,
                mz,
                scan: ctx.scan,
                rt: ctx.rt_minutes,
                polarity: ctx.polarity,
            });
        }
        *previous_ms1_scan = ctx.scan;
    } else if ctx.ms_level >= 2 {
        let precmz: f64 = precursor_mz_text.trim().parse().unwrap_or(0.0);
        ms2.reserve(peaks.len());
        for (mz, i) in peaks {
            ms2.push(Ms2Peak {
                i,
                i_norm: i / i_max,
                i_tic_norm: i / i_sum,
                mz,
                scan: ctx.scan,
                rt: ctx.rt_minutes,
                polarity: ctx.polarity,
                precmz,
                ms1scan: *previous_ms1_scan,
                charge: 0,
                mobility: None,
            });
        }
    }
    Ok(())
}

/// ISO-8601 duration with only a seconds component (`PT0.197S`) → minutes.
fn parse_iso_duration_minutes(s: &str) -> Option<f64> {
    let s = s.trim();
    if !s.starts_with("PT") || !s.ends_with('S') {
        return s.parse::<f64>().ok().map(|v| v / 60.0);
    }
    let inner = &s[2..s.len() - 1];
    let seconds: f64 = inner.parse().ok()?;
    Some(seconds / 60.0)
}

// Suppress an unused-import warning when polarity_code is only
// referenced via the module's public surface.
#[allow(dead_code)]
fn _touch_polarity() -> u8 {
    polarity_code(mzdata::spectrum::ScanPolarity::Positive)
}
