//! MassQL query execution engine — Rust port of `msql_engine.py` +
//! `msql_engine_filters.py`.
//!
//! Scope of this first pass:
//!
//! * Single-query, non-variable WHERE / FILTER clauses.
//! * Conditions: MS2PROD, MS2PREC, MS2NL, MS1MZ, RTMIN/MAX, SCANMIN/MAX,
//!   POLARITY, CHARGE.
//! * Qualifiers: TOLERANCEMZ, TOLERANCEPPM, INTENSITYPERCENT,
//!   INTENSITYVALUE, INTENSITYTICPERCENT (all comparators), EXCLUDED.
//! * Query functions: `scaninfo`, `scansum`, `scannum`, `scanmz`, plus
//!   the bare `MS1DATA`/`MS2DATA` pass-through.
//!
//! Not yet ported (all cleanly unreachable — the engine returns a
//! `Semantic` error if encountered): X/Y variable queries,
//! INTENSITYMATCH, MASSDEFECT, MOBILITY range, CARDINALITY,
//! OTHERSCAN. The CLI surfaces the error verbatim so missing support is
//! obvious in diff tests rather than silently dropped.

use massql_loader::{Dataset, Ms1Peak, Ms2Peak};
use massql_parser::parse_msql;
use serde_json::Value;
use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};
use thiserror::Error;

pub mod expr;
pub mod filters;
pub mod result;
pub mod variable;

pub use result::{QueryResult, ResultRow};

#[derive(Debug, Error)]
pub enum EngineError {
    #[error("parse: {0}")]
    Parse(String),
    #[error("semantic: {0}")]
    Semantic(String),
}

/// Top-level entry point. Parses `query`, runs it against `dataset`,
/// returns a row-oriented result ready for TSV serialization.
pub fn process_query(query: &str, dataset: &Dataset) -> Result<QueryResult, EngineError> {
    let parsed = parse_msql(query).map_err(|e| EngineError::Parse(e.to_string()))?;
    // The variable pipeline owns the whole dispatch when `X` / `Y`
    // appear; otherwise we fall through to the concrete path below.
    if let Some(result) = variable::run_if_variable(&parsed, dataset)? {
        return Ok(result);
    }
    process_query_prepared(&parsed, dataset)
}

/// Run a parsed (and, if needed, X-substituted) query against a dataset.
///
/// Shared by the top-level entry point and the variable pipeline —
/// the latter substitutes X into the parse tree then calls back in
/// once per candidate. Kept on the public surface so
/// [`variable::run_if_variable`] can invoke it without going back
/// through the parser.
pub fn process_query_prepared(parsed: &Value, dataset: &Dataset) -> Result<QueryResult, EngineError> {
    process_query_prepared_from(parsed, Filtered::from_dataset(dataset))
}

/// Same as [`process_query_prepared`] but starts from a pre-filtered
/// state. The variable pipeline uses this to hand every candidate
/// the already-narrowed ms1/ms2 peak set — matching Python's
/// `_executeconditions_query(..., ms1_input_df=narrowed, ...)`. It
/// avoids re-applying RT / polarity / scan-range filters N times
/// (once per X candidate), which was a big hit on long queries.
pub fn process_query_prepared_from(
    parsed: &Value,
    start: Filtered,
) -> Result<QueryResult, EngineError> {
    let querytype = parsed
        .get("querytype")
        .ok_or_else(|| EngineError::Semantic("missing querytype".into()))?;
    let conditions = parsed
        .get("conditions")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    reset_register();
    let ordered = reorder_reference_first(&conditions);
    let filtered = apply_conditions_to_state(&ordered, start)?;
    result::collate(querytype, &filtered)
}

fn reorder_reference_first(conditions: &[Value]) -> Vec<Value> {
    let (refs, rest): (Vec<_>, Vec<_>) = conditions
        .iter()
        .cloned()
        .partition(|c| {
            c.get("qualifiers")
                .and_then(|q| q.get("qualifierintensityreference"))
                .is_some()
        });
    refs.into_iter().chain(rest.into_iter()).collect()
}

/// Expose the condition-application step for the variable pipeline's
/// pre-search (Python's `_executeconditions_query` on the
/// variable-free subset of conditions).
pub fn apply_conditions_raw(conditions: &[Value], dataset: &Dataset) -> Result<Filtered, EngineError> {
    apply_conditions(conditions, dataset)
}

/// Carries the filtered peaks through the pipeline. We keep clones of
/// the input vectors — since `mz_tol` / `intensity` filters keep
/// narrowing monotonically, we always shrink, never need the originals
/// to recover (except for the MS1 filter path, which takes the
/// original MS1 for scan-linking — left as TODO).
#[derive(Debug, Clone, Default)]
pub struct Filtered {
    pub ms1: Vec<Ms1Peak>,
    pub ms2: Vec<Ms2Peak>,
    /// Python's FILTER step adds an `mz_defect = mz - int(mz)` column
    /// to its DataFrame whenever the MASSDEFECT qualifier fires; that
    /// column then leaks into the CSV output. We don't actually store
    /// per-peak defect — it's `mz - mz.floor()` at output time — but
    /// we track whether the column should appear.
    pub mz_defect_column: bool,
}

impl Filtered {
    fn from_dataset(ds: &Dataset) -> Self {
        Self {
            ms1: ds.ms1.clone(),
            ms2: ds.ms2.clone(),
            mz_defect_column: false,
        }
    }
}

fn apply_conditions(conditions: &[Value], dataset: &Dataset) -> Result<Filtered, EngineError> {
    apply_conditions_to_state(conditions, Filtered::from_dataset(dataset))
}

fn apply_conditions_to_state(
    conditions: &[Value],
    mut state: Filtered,
) -> Result<Filtered, EngineError> {

    // ----- Scan-level filters (RT, polarity, scan-number, charge) -----
    //
    // Python applies these in one pass before peak-level filters,
    // because they commute and there's no "intersect with previous"
    // step — a row either satisfies the predicate or it doesn't.
    for cond in conditions {
        if cond["conditiontype"] != "where" {
            continue;
        }
        let ctype = cond["type"].as_str().unwrap_or("");
        let value = &cond["value"];
        match ctype {
            "rtmincondition" => {
                let rt = value[0].as_f64().unwrap_or(0.0);
                state.ms1.retain(|p| p.rt > rt);
                state.ms2.retain(|p| p.rt > rt);
            }
            "rtmaxcondition" => {
                let rt = value[0].as_f64().unwrap_or(0.0);
                state.ms1.retain(|p| p.rt < rt);
                state.ms2.retain(|p| p.rt < rt);
            }
            "scanmincondition" => {
                let s = value[0].as_f64().unwrap_or(0.0) as u32;
                state.ms1.retain(|p| p.scan >= s);
                state.ms2.retain(|p| p.scan >= s);
            }
            "scanmaxcondition" => {
                let s = value[0].as_f64().unwrap_or(0.0) as u32;
                state.ms1.retain(|p| p.scan <= s);
                state.ms2.retain(|p| p.scan <= s);
            }
            "polaritycondition" => {
                let want = match value[0].as_str().unwrap_or("") {
                    "positivepolarity" => 1u8,
                    "negativepolarity" => 2u8,
                    _ => 0,
                };
                state.ms1.retain(|p| p.polarity == want);
                state.ms2.retain(|p| p.polarity == want);
            }
            "chargecondition" => {
                let c = value[0].as_f64().unwrap_or(0.0) as i32;
                state.ms2.retain(|p| p.charge == c);
                // Link back to MS1 through ms1scan — matches Python.
                let ms1scans: BTreeSet<u32> = state.ms2.iter().map(|p| p.ms1scan).collect();
                state.ms1.retain(|p| ms1scans.contains(&p.scan));
            }
            "mobilitycondition" => {
                // MOBILITY=range(min=N, max=M) — `min`/`max` may be
                // string expressions (containing X) which we can't
                // resolve without a variable pipeline; only literals
                // are supported for now.
                //
                // Python's behavior when the ms2_df has no `mobility`
                // column at all (which it doesn't when no spectrum
                // carried ion mobility): the filter is a silent no-op.
                // We match that by short-circuiting when every peak's
                // mobility is None.
                let any_mobility = state.ms2.iter().any(|p| p.mobility.is_some());
                if !any_mobility {
                    continue;
                }
                let min = cond
                    .get("min")
                    .and_then(|v| v.as_f64())
                    .ok_or_else(|| EngineError::Semantic(
                        "MOBILITY min/max must be a literal number (variable expressions \
                         not yet supported in the Rust engine)".into(),
                    ))?;
                let max = cond
                    .get("max")
                    .and_then(|v| v.as_f64())
                    .ok_or_else(|| EngineError::Semantic(
                        "MOBILITY min/max must be a literal number (variable expressions \
                         not yet supported in the Rust engine)".into(),
                    ))?;
                state
                    .ms2
                    .retain(|p| matches!(p.mobility, Some(m) if m >= min && m <= max));
                // ms1 doesn't carry mobility in our loader.
            }
            _ => {}
        }
    }

    // ----- Peak-level WHERE conditions -----
    for cond in conditions {
        if cond["conditiontype"] != "where" {
            continue;
        }
        let ctype = cond["type"].as_str().unwrap_or("");
        match ctype {
            "ms2productcondition" => {
                filters::apply_ms2prod(cond, &mut state)?;
            }
            "ms2precursorcondition" => {
                filters::apply_ms2prec(cond, &mut state)?;
            }
            "ms2neutrallosscondition" => {
                filters::apply_ms2nl(cond, &mut state)?;
            }
            "ms1mzcondition" => {
                filters::apply_ms1mz(cond, &mut state)?;
            }
            // Scan-level filters handled above.
            "rtmincondition" | "rtmaxcondition" | "scanmincondition" | "scanmaxcondition"
            | "polaritycondition" | "chargecondition" | "mobilitycondition" => continue,
            "xcondition" => {
                return Err(EngineError::Semantic(
                    "X variable queries are not yet supported in the Rust port".into(),
                ));
            }
            other => {
                return Err(EngineError::Semantic(format!(
                    "unhandled condition type: {}",
                    other
                )));
            }
        }
    }

    // ----- FILTER clause (peak-level, not scan-level) -----
    for cond in conditions {
        if cond["conditiontype"] != "filter" {
            continue;
        }
        let ctype = cond["type"].as_str().unwrap_or("");
        match ctype {
            "ms1mzcondition" => filters::filter_ms1mz(cond, &mut state)?,
            "ms2productcondition" => filters::filter_ms2prod(cond, &mut state)?,
            _ => {
                return Err(EngineError::Semantic(format!(
                    "unhandled FILTER condition: {}",
                    ctype
                )));
            }
        }
    }

    Ok(state)
}

/// Helpers exposed for filter module.
pub(crate) fn qualifier(cond: &Value) -> Option<&Value> {
    cond.get("qualifiers")
}

/// Computes the m/z tolerance for a peak match, mirroring
/// `_get_mz_tolerance`: ppm wins over Da, default 0.1 Da.
pub(crate) fn mz_tolerance(q: Option<&Value>, mz: f64) -> f64 {
    let q = match q {
        Some(v) => v,
        None => return 0.1,
    };
    if let Some(ppm) = q.get("qualifierppmtolerance").and_then(|v| v["value"].as_f64()) {
        return (ppm * mz / 1_000_000.0).abs();
    }
    if let Some(da) = q.get("qualifiermztolerance").and_then(|v| v["value"].as_f64()) {
        return da;
    }
    0.1
}

/// Intensity filter, mirroring `_get_intensity_mask`: three columns
/// (i, i_norm, i_tic_norm) each gated by the matching qualifier, with
/// `>` as the default comparator. Returns a predicate closure so it
/// can be shared between MS1 and MS2 paths.
#[derive(Debug, Clone, Copy)]
pub(crate) struct IntensityPredicate {
    pub i_thresh: f32,
    pub i_cmp: Comparator,
    pub i_norm_thresh: f32,
    pub i_norm_cmp: Comparator,
    pub i_tic_thresh: f32,
    pub i_tic_cmp: Comparator,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Comparator {
    Greater,
    Less,
    GreaterEqual,
    Default, // bare ">0" fallback when no qualifier supplied
}

impl IntensityPredicate {
    pub fn from_qualifier(q: Option<&Value>) -> Self {
        let mut me = IntensityPredicate {
            i_thresh: 0.0,
            i_cmp: Comparator::Default,
            i_norm_thresh: 0.0,
            i_norm_cmp: Comparator::Default,
            i_tic_thresh: 0.0,
            i_tic_cmp: Comparator::Default,
        };
        let Some(q) = q else { return me };

        for (key, field) in &[
            ("qualifierintensityvalue", "i"),
            ("qualifierintensitypercent", "i_norm"),
            ("qualifierintensityticpercent", "i_tic_norm"),
        ] {
            let Some(sub) = q.get(*key) else { continue };
            let scale = match *field {
                "i" => 1.0_f32,
                _ => 100.0_f32, // percent qualifiers are stored as 0..100
            };
            let mut val = sub["value"].as_f64().unwrap_or(0.0) as f32 / scale;
            let comp = sub
                .get("comparator")
                .and_then(|v| v.as_str())
                .unwrap_or("greaterthan");

            let cmp = match comp {
                "greaterthan" => {
                    if scale > 1.0 {
                        // Python caps the percent threshold at 0.99 so
                        // `>100` queries aren't silently empty.
                        val = val.min(0.99);
                    }
                    Comparator::Greater
                }
                "lessthan" => Comparator::Less,
                _ => Comparator::GreaterEqual,
            };

            match *field {
                "i" => {
                    me.i_thresh = val;
                    me.i_cmp = cmp;
                }
                "i_norm" => {
                    me.i_norm_thresh = val;
                    me.i_norm_cmp = cmp;
                }
                "i_tic_norm" => {
                    me.i_tic_thresh = val;
                    me.i_tic_cmp = cmp;
                }
                _ => unreachable!(),
            }
        }
        me
    }

    pub fn matches(&self, i: f32, i_norm: f32, i_tic: f32) -> bool {
        Self::check(i, self.i_thresh, self.i_cmp)
            && Self::check(i_norm, self.i_norm_thresh, self.i_norm_cmp)
            && Self::check(i_tic, self.i_tic_thresh, self.i_tic_cmp)
    }

    fn check(val: f32, thresh: f32, cmp: Comparator) -> bool {
        match cmp {
            Comparator::Greater => val > thresh,
            Comparator::Less => val < thresh,
            Comparator::GreaterEqual => val >= thresh,
            // Default path: `> 0`.
            Comparator::Default => val > 0.0,
        }
    }
}

/// EXCLUDED qualifier — invert the scan set for the condition.
pub(crate) fn exclusion_flag(q: Option<&Value>) -> bool {
    q.and_then(|v| v.get("qualifierexcluded")).is_some()
}

/// For a given filtered-peak set, restrict both `state.ms2` and
/// `state.ms1` so that only scans present in `filtered_ms2_scans`
/// survive (MS1 via the reverse `ms1scan` link).
pub(crate) fn restrict_to_ms2_scans(state: &mut Filtered, scans: &BTreeSet<u32>) {
    state.ms2.retain(|p| scans.contains(&p.scan));
    let linked: BTreeSet<u32> = state.ms2.iter().map(|p| p.ms1scan).collect();
    state.ms1.retain(|p| linked.contains(&p.scan));
}

/// For the MS1 condition: once we have a set of surviving MS1 scans,
/// restrict both ms1 and ms2 accordingly (ms2 via `ms1scan`).
pub(crate) fn restrict_to_ms1_scans(state: &mut Filtered, scans: &BTreeSet<u32>) {
    state.ms1.retain(|p| scans.contains(&p.scan));
    state.ms2.retain(|p| scans.contains(&p.ms1scan));
}

// Keep an import for consumers.
pub(crate) fn _scans_ms2(peaks: &[Ms2Peak]) -> BTreeSet<u32> {
    peaks.iter().map(|p| p.scan).collect()
}

pub(crate) fn _scans_ms1(peaks: &[Ms1Peak]) -> BTreeSet<u32> {
    peaks.iter().map(|p| p.scan).collect()
}

/// Per-scan intensity register for INTENSITYMATCH / REFERENCE
/// resolution. Keyed by the raw match-variable string (typically
/// `"Y"`) that appears as the reference condition's value. Values are
/// the per-scan sum of filtered-peak intensities from the reference
/// condition.
///
/// Ported from the `register_dict` parameter passed around in
/// `msql_engine.py` + `msql_engine_filters.py`. We wrap it in
/// `RefCell` so filter functions can borrow it mutably without
/// threading a `&mut` through every call site.
#[derive(Debug, Default)]
pub(crate) struct IntensityRegister {
    pub map: BTreeMap<(u32, String), f64>,
}

impl IntensityRegister {
    pub fn new() -> Self {
        Self { map: BTreeMap::new() }
    }
}

thread_local! {
    pub(crate) static REGISTER: RefCell<IntensityRegister> = RefCell::new(IntensityRegister::new());
}

fn with_register<T>(f: impl FnOnce(&mut IntensityRegister) -> T) -> T {
    REGISTER.with(|r| f(&mut r.borrow_mut()))
}

/// Reset the register at the start of each top-level query so state
/// doesn't leak between calls.
fn reset_register() {
    REGISTER.with(|r| r.borrow_mut().map.clear());
}
