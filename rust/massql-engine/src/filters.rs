//! Per-condition peak filters. Each function narrows the
//! [`crate::Filtered`] state in place; the semantics mirror the
//! equivalent functions in `msql_engine_filters.py`.

use std::collections::{BTreeMap, BTreeSet};

use massql_loader::{Ms1Peak, Ms2Peak};
use serde_json::Value;

use crate::{
    exclusion_flag, expr, mz_tolerance, qualifier, restrict_to_ms1_scans, restrict_to_ms2_scans,
    with_register, EngineError, Filtered, IntensityPredicate,
};

fn numeric_values(cond: &Value) -> Result<Vec<f64>, EngineError> {
    let arr = cond
        .get("value")
        .and_then(|v| v.as_array())
        .ok_or_else(|| EngineError::Semantic("condition missing value array".into()))?;
    arr.iter()
        .map(|v| {
            v.as_f64().ok_or_else(|| {
                EngineError::Semantic(format!(
                    "variable / string values not yet supported in the Rust engine: {}",
                    v
                ))
            })
        })
        .collect()
}

/// For filters that accept a MASSDEFECT qualifier, return `(min, max)`
/// in 0..1, defaulting to the full range when absent.
fn massdefect_window(q: Option<&Value>) -> (f64, f64) {
    match q.and_then(|v| v.get("qualifiermassdefect")) {
        Some(md) => {
            let min = md.get("min").and_then(|v| v.as_f64()).unwrap_or(0.0);
            let max = md.get("max").and_then(|v| v.as_f64()).unwrap_or(1.0);
            (min, max)
        }
        None => (0.0, 1.0),
    }
}

fn has_massdefect(q: Option<&Value>) -> bool {
    let (min, max) = massdefect_window(q);
    min > 0.0 || max < 1.0
}

/// Peak mass defect = `mz - floor(mz)` (`mz - mz.astype(int)` in Python).
#[inline]
fn mz_defect(mz: f64) -> f64 {
    mz - mz.floor()
}

/// `CARDINALITY=range(min=A, max=B)` / `MATCHCOUNT=range(min=A, max=B)`
/// — constrains *how many of the OR'd target m/z values* must match
/// per scan. Returns `(min, max)` with defaults `(1, usize::MAX)` so
/// the gate is a no-op when absent (= "at least one", which is the
/// normal OR semantics).
fn cardinality_range(q: Option<&Value>) -> (usize, usize) {
    match q.and_then(|v| v.get("qualifiercardinality")) {
        Some(c) => {
            let min = c.get("min").and_then(|v| v.as_f64()).unwrap_or(1.0) as usize;
            let max = c
                .get("max")
                .and_then(|v| v.as_f64())
                .map(|v| v as usize)
                .unwrap_or(usize::MAX);
            (min.max(1), max)
        }
        None => (1, usize::MAX),
    }
}

/// Shared helper that takes the per-scan set of matched target
/// indices and reduces it to the scans passing cardinality + exclusion.
fn finalize_scans(
    scan_targets: BTreeMap<u32, BTreeSet<usize>>,
    original_scans: impl FnOnce() -> BTreeSet<u32>,
    q: Option<&Value>,
) -> BTreeSet<u32> {
    let (card_min, card_max) = cardinality_range(q);
    let mut matched: BTreeSet<u32> = scan_targets
        .into_iter()
        .filter(|(_, targets)| targets.len() >= card_min && targets.len() <= card_max)
        .map(|(scan, _)| scan)
        .collect();

    if exclusion_flag(q) {
        matched = original_scans().difference(&matched).copied().collect();
    }
    matched
}

// ==================== INTENSITYMATCH register ====================

/// If this condition sets a reference (`INTENSITYMATCHREFERENCE`),
/// record per-scan intensity sums into the global register. `sums`
/// is the per-scan sum of filtered-peak intensities produced by this
/// condition's match.
fn maybe_set_register(cond: &Value, sums: &BTreeMap<u32, f64>) {
    let Some(q) = cond.get("qualifiers") else { return };
    if q.get("qualifierintensityreference").is_none() {
        return;
    }
    let Some(variable) = q
        .get("qualifierintensitymatch")
        .and_then(|m| m.get("value"))
        .and_then(|v| v.as_str())
    else {
        return;
    };
    with_register(|r| {
        for (&scan, &sum) in sums {
            r.map.insert((scan, variable.to_string()), sum);
        }
    });
}

/// If this condition has an INTENSITYMATCH + INTENSITYMATCHPERCENT,
/// narrow `scans_sums` to only those scans whose summed intensity
/// lies within (evaluated - tol, evaluated + tol) where `evaluated`
/// is the match expression (`Y*0.66`, etc.) evaluated with Y bound to
/// the register value.
///
/// Mirrors `_filter_intensitymatch` in `msql_engine_filters.py`,
/// including the quirk that Python looks up the register under the
/// *first character* of the match expression rather than the full
/// string.
fn maybe_match_register(cond: &Value, sums: &mut BTreeMap<u32, f64>) {
    let Some(q) = cond.get("qualifiers") else { return };
    let (Some(match_expr), Some(tol_pct)) = (
        q.get("qualifierintensitymatch")
            .and_then(|m| m.get("value"))
            .and_then(|v| v.as_str())
            .map(str::to_string),
        q.get("qualifierintensitytolpercent")
            .and_then(|t| t.get("value"))
            .and_then(|v| v.as_f64()),
    ) else {
        return;
    };
    // Python's convention: variable name is the first char of the
    // match expression (e.g. `"Y"` from `"Y*0.66"`).
    let variable = match match_expr.chars().next() {
        Some(c) => c.to_string(),
        None => return,
    };

    let keep: BTreeSet<u32> = sums
        .iter()
        .filter_map(|(&scan, &sum)| {
            let register_value = with_register(|r| r.map.get(&(scan, variable.clone())).copied())?;
            let mut env = std::collections::HashMap::new();
            env.insert(variable.clone(), register_value);
            let evaluated = match expr::eval(&match_expr, &env) {
                Ok(v) => v,
                Err(_) => return None,
            };
            let tol = (tol_pct / 100.0) * evaluated;
            let min = evaluated - tol;
            let max = evaluated + tol;
            if sum > min && sum < max {
                Some(scan)
            } else {
                None
            }
        })
        .collect();
    sums.retain(|s, _| keep.contains(s));
}

/// Returns `(mz_min, mz_max)` — the Python filter uses strict `>` /
/// `<`, so we keep the same open-interval convention.
fn mz_window(q: Option<&Value>, mz: f64) -> (f64, f64) {
    let tol = mz_tolerance(q, mz);
    (mz - tol, mz + tol)
}

// ==================== MS2PROD ====================

pub fn apply_ms2prod(cond: &Value, state: &mut Filtered) -> Result<(), EngineError> {
    if state.ms2.is_empty() {
        return Ok(());
    }
    let q = qualifier(cond);
    let intensity = IntensityPredicate::from_qualifier(q);
    let values = numeric_values(cond)?;
    let (md_min, md_max) = massdefect_window(q);
    let md_gate = has_massdefect(q);

    // OR-list: record which target indices each scan matched + the
    // per-scan summed intensity of matching peaks (the latter feeds
    // the INTENSITYMATCH register machinery).
    let mut scan_targets: BTreeMap<u32, BTreeSet<usize>> = BTreeMap::new();
    let mut scan_sums: BTreeMap<u32, f64> = BTreeMap::new();
    for (idx, target) in values.iter().enumerate() {
        let (lo, hi) = mz_window(q, *target);
        for p in &state.ms2 {
            if p.mz > lo
                && p.mz < hi
                && intensity.matches(p.i, p.i_norm, p.i_tic_norm)
            {
                if md_gate {
                    let d = mz_defect(p.mz);
                    if d <= md_min || d >= md_max {
                        continue;
                    }
                }
                scan_targets.entry(p.scan).or_default().insert(idx);
                *scan_sums.entry(p.scan).or_insert(0.0) += p.i as f64;
            }
        }
    }

    // INTENSITYMATCH: possibly set the register (reference condition)
    // and possibly filter by it (matching condition). Order matches
    // Python's `_set_intensity_register` then `_filter_intensitymatch`.
    maybe_set_register(cond, &scan_sums);
    maybe_match_register(cond, &mut scan_sums);
    scan_targets.retain(|s, _| scan_sums.contains_key(s));

    let matched_scans = finalize_scans(
        scan_targets,
        || state.ms2.iter().map(|p| p.scan).collect(),
        q,
    );

    if matched_scans.is_empty() {
        state.ms1.clear();
        state.ms2.clear();
        return Ok(());
    }
    restrict_to_ms2_scans(state, &matched_scans);
    Ok(())
}

// ==================== MS2PREC ====================

pub fn apply_ms2prec(cond: &Value, state: &mut Filtered) -> Result<(), EngineError> {
    if state.ms2.is_empty() {
        return Ok(());
    }
    let q = qualifier(cond);
    let values = numeric_values(cond)?;
    let (md_min, md_max) = massdefect_window(q);
    let md_gate = has_massdefect(q);

    let mut scan_targets: BTreeMap<u32, BTreeSet<usize>> = BTreeMap::new();
    let mut scan_sums: BTreeMap<u32, f64> = BTreeMap::new();
    for (idx, target) in values.iter().enumerate() {
        let (lo, hi) = mz_window(q, *target);
        for p in &state.ms2 {
            if p.precmz > lo && p.precmz < hi {
                if md_gate {
                    let d = mz_defect(p.precmz);
                    if d <= md_min || d >= md_max {
                        continue;
                    }
                }
                scan_targets.entry(p.scan).or_default().insert(idx);
                *scan_sums.entry(p.scan).or_insert(0.0) += p.i as f64;
            }
        }
    }

    maybe_set_register(cond, &scan_sums);
    maybe_match_register(cond, &mut scan_sums);
    scan_targets.retain(|s, _| scan_sums.contains_key(s));

    let matched_scans = finalize_scans(
        scan_targets,
        || state.ms2.iter().map(|p| p.scan).collect(),
        q,
    );

    if matched_scans.is_empty() {
        state.ms1.clear();
        state.ms2.clear();
        return Ok(());
    }
    restrict_to_ms2_scans(state, &matched_scans);
    Ok(())
}

// ==================== MS2NL (neutral loss) ====================

pub fn apply_ms2nl(cond: &Value, state: &mut Filtered) -> Result<(), EngineError> {
    if state.ms2.is_empty() {
        return Ok(());
    }
    let q = qualifier(cond);
    let intensity = IntensityPredicate::from_qualifier(q);
    let values = numeric_values(cond)?;
    let (md_min, md_max) = massdefect_window(q);
    let md_gate = has_massdefect(q);

    let mut scan_targets: BTreeMap<u32, BTreeSet<usize>> = BTreeMap::new();
    let mut scan_sums: BTreeMap<u32, f64> = BTreeMap::new();
    for (idx, target) in values.iter().enumerate() {
        // NOTE: Python uses `_get_mz_tolerance(q, mz)` — same as prod;
        // the tolerance is computed against the target NL, not the
        // precursor. Keep that behavior.
        let (lo, hi) = mz_window(q, *target);
        for p in &state.ms2 {
            let nl = p.precmz - p.mz;
            if nl > lo
                && nl < hi
                && intensity.matches(p.i, p.i_norm, p.i_tic_norm)
            {
                if md_gate {
                    let d = mz_defect(nl);
                    if d <= md_min || d >= md_max {
                        continue;
                    }
                }
                scan_targets.entry(p.scan).or_default().insert(idx);
                *scan_sums.entry(p.scan).or_insert(0.0) += p.i as f64;
            }
        }
    }

    maybe_set_register(cond, &scan_sums);
    maybe_match_register(cond, &mut scan_sums);
    scan_targets.retain(|s, _| scan_sums.contains_key(s));

    let matched_scans = finalize_scans(
        scan_targets,
        || state.ms2.iter().map(|p| p.scan).collect(),
        q,
    );

    if matched_scans.is_empty() {
        state.ms1.clear();
        state.ms2.clear();
        return Ok(());
    }
    restrict_to_ms2_scans(state, &matched_scans);
    Ok(())
}

// ==================== MS1MZ ====================

pub fn apply_ms1mz(cond: &Value, state: &mut Filtered) -> Result<(), EngineError> {
    if state.ms1.is_empty() {
        return Ok(());
    }
    let q = qualifier(cond);
    let intensity = IntensityPredicate::from_qualifier(q);
    let values = numeric_values(cond)?;
    let (md_min, md_max) = massdefect_window(q);
    let md_gate = has_massdefect(q);

    let mut scan_targets: BTreeMap<u32, BTreeSet<usize>> = BTreeMap::new();
    let mut scan_sums: BTreeMap<u32, f64> = BTreeMap::new();
    for (idx, target) in values.iter().enumerate() {
        let (lo, hi) = mz_window(q, *target);
        for p in &state.ms1 {
            if p.mz > lo
                && p.mz < hi
                && intensity.matches(p.i, p.i_norm, p.i_tic_norm)
            {
                if md_gate {
                    let d = mz_defect(p.mz);
                    if d <= md_min || d >= md_max {
                        continue;
                    }
                }
                scan_targets.entry(p.scan).or_default().insert(idx);
                *scan_sums.entry(p.scan).or_insert(0.0) += p.i as f64;
            }
        }
    }

    maybe_set_register(cond, &scan_sums);
    maybe_match_register(cond, &mut scan_sums);
    scan_targets.retain(|s, _| scan_sums.contains_key(s));

    let matched_scans = finalize_scans(
        scan_targets,
        || state.ms1.iter().map(|p| p.scan).collect(),
        q,
    );

    if matched_scans.is_empty() {
        state.ms1.clear();
        state.ms2.clear();
        return Ok(());
    }
    restrict_to_ms1_scans(state, &matched_scans);
    Ok(())
}

// ==================== FILTER clause ====================
//
// In FILTER mode, we don't kick whole scans out — we just drop the
// peaks that don't match, leaving the surviving scans intact.

pub fn filter_ms1mz(cond: &Value, state: &mut Filtered) -> Result<(), EngineError> {
    if state.ms1.is_empty() {
        return Ok(());
    }
    let q = qualifier(cond);
    let intensity = IntensityPredicate::from_qualifier(q);
    let values = numeric_values(cond)?;
    let (md_min, md_max) = massdefect_window(q);
    let md_gate = has_massdefect(q);
    if md_gate {
        // Python's FILTER path adds an `mz_defect` column when the
        // MASSDEFECT qualifier is present; flag the state so collation
        // emits it.
        state.mz_defect_column = true;
    }

    state.ms1.retain(|p: &Ms1Peak| {
        if !intensity.matches(p.i, p.i_norm, p.i_tic_norm) {
            return false;
        }
        if md_gate {
            let d = mz_defect(p.mz);
            if d <= md_min || d >= md_max {
                return false;
            }
        }
        values.iter().any(|&target| {
            let (lo, hi) = mz_window(q, target);
            p.mz > lo && p.mz < hi
        })
    });
    Ok(())
}

pub fn filter_ms2prod(cond: &Value, state: &mut Filtered) -> Result<(), EngineError> {
    if state.ms2.is_empty() {
        return Ok(());
    }
    let q = qualifier(cond);
    let intensity = IntensityPredicate::from_qualifier(q);
    let values = numeric_values(cond)?;
    if has_massdefect(q) {
        state.mz_defect_column = true;
    }

    state.ms2.retain(|p: &Ms2Peak| {
        if !intensity.matches(p.i, p.i_norm, p.i_tic_norm) {
            return false;
        }
        values.iter().any(|&target| {
            let (lo, hi) = mz_window(q, target);
            p.mz > lo && p.mz < hi
        })
    });
    Ok(())
}
