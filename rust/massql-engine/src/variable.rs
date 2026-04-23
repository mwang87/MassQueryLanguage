//! Rust port of `_evalute_variable_query` in `massql/msql_engine.py`.
//!
//! The variable pipeline handles queries where `X` (and sometimes `Y`)
//! stands in for a mass that must be discovered from the data itself.
//! A query like:
//!
//! ```text
//!   QUERY scaninfo(MS2DATA) WHERE MS2PROD=X AND MS2PROD=X+164.9
//! ```
//!
//! doesn't have a concrete target m/z — we have to try every candidate
//! `X` (every MS2 product-ion m/z in the file) and keep the candidates
//! where *both* conditions are satisfied. The algorithm mirrors
//! Python's:
//!
//! 1. Collect X-binding hints from conditions (`query_ms1` vs
//!    `query_ms2` vs `query_ms2prec`).
//! 2. Optionally honor `X=range(min=A, max=B)` and
//!    `X=massdefect(min=A, max=B)` restrictions.
//! 3. Run a "pre-search" with only the non-variable conditions to
//!    narrow down which scans are in play.
//! 4. Collect candidate X values from the surviving peak column(s),
//!    dedupe by the smallest mz tolerance present on any X-binding
//!    condition.
//! 5. For each candidate: substitute `X` into every condition (values,
//!    qualifier mins/maxes, mobility ranges) and run the concrete
//!    query via the non-variable engine path.
//! 6. Concat all per-candidate result rows, dedupe by (scan, X) using
//!    the truncated-int comment trick.
//!
//! INTENSITYMATCH / INTENSITYMATCHREFERENCE (the `Y` side of things)
//! is **not** handled in this phase — when a query uses it, Python's
//! engine relies on a reference register that we haven't ported. We
//! still substitute `X` into `Y*(0.0608+(2e-06*X))` so the string
//! reaches the engine in its final form, but the register logic
//! that validates it is a TODO.

use std::collections::{BTreeMap, BTreeSet, HashMap};

use massql_loader::Dataset;
use serde_json::{json, Value};

use crate::{expr, process_query_prepared_from, EngineError};

/// High-level properties extracted once per query.
#[derive(Debug, Default)]
struct VarProps {
    has_variable: bool,
    query_ms1: bool,
    query_ms2: bool,
    query_ms2prec: bool,
    /// `X=range(min=.., max=..)` — narrows the candidate space.
    min: f64,
    max: f64,
    mindefect: f64,
    maxdefect: f64,
    /// Smallest m/z tolerance (Da + ppm) across every variable-using
    /// condition. Used to dedupe candidates.
    ppm_tolerance: f64,
    da_tolerance: f64,
}

impl VarProps {
    fn new() -> Self {
        VarProps {
            min: 0.0,
            max: 1_000_000.0,
            mindefect: 0.0,
            maxdefect: 1.0,
            ppm_tolerance: 100_000.0,
            da_tolerance: 100_000.0,
            ..Default::default()
        }
    }
}

/// Returns `Some(result)` if this query needs the variable pipeline
/// (and runs it), or `None` if there's no variable — in which case
/// the caller should use the normal concrete path.
pub fn run_if_variable(
    parsed: &Value,
    dataset: &Dataset,
) -> Result<Option<crate::QueryResult>, EngineError> {
    let conditions = parsed
        .get("conditions")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    let props = analyze_conditions(&conditions);
    if !props.has_variable {
        return Ok(None);
    }

    // Step 1: run a pre-search using only the non-variable conditions
    // — narrows down the peak set we'll pull X candidates from.
    let mut presearch = parsed.clone();
    let non_var_conds: Vec<Value> = conditions
        .iter()
        .filter(|c| !has_variable_in_condition(c))
        .cloned()
        .collect();
    presearch["conditions"] = Value::Array(non_var_conds.clone());

    // Run the non-variable conditions via the engine's normal path
    // against the raw dataset. The result state carries the narrowed
    // (ms1, ms2) peak lists into the candidate enumeration below.
    let mut narrowed = crate::apply_conditions_raw(&non_var_conds, dataset)?;

    // Step 1.5: Python pre-filters the candidate peak set by the
    // intensity mask of any X-binding MS1 condition — otherwise low-
    // intensity peaks that couldn't possibly satisfy the reference's
    // INTENSITYPERCENT=5 (say) still get tried, producing spurious
    // matches. Mirror the Python logic here.
    apply_variable_intensity_prefilter(&conditions, &mut narrowed);

    // Step 2: pick candidate m/z values.
    let candidates = collect_candidates(&props, &narrowed);

    // Step 3: for each candidate, substitute and run.
    let querytype = parsed.get("querytype").cloned().unwrap_or(Value::Null);
    let mut combined: BTreeMap<(u32, Option<i64>), crate::ResultRow> = BTreeMap::new();
    let mut columns_present = crate::result::ColumnSet::default();

    for candidate in candidates {
        // X range + defect gates.
        if candidate < props.min || candidate > props.max {
            continue;
        }
        let defect = candidate - candidate.floor();
        if defect < props.mindefect || defect > props.maxdefect {
            continue;
        }

        let substituted_conds = substitute_conditions(&conditions, candidate);

        // Run the concrete query against the original dataset (not
        // the pre-filtered one — Python does this, and it matters for
        // conditions that depend on other scans).
        let mut concrete = serde_json::Map::new();
        concrete.insert("querytype".into(), querytype.clone());
        concrete.insert("conditions".into(), Value::Array(substituted_conds));
        let concrete_val = Value::Object(concrete);

        // Hand each candidate the pre-narrowed state Python calls
        // `ms1_df`/`ms2_df`. Matches Python's
        //   `_executeconditions_query(..., ms1_input_df=ms1_df, ms2_input_df=ms2_df, ...)`
        // inside the per-candidate loop. Avoids re-applying RT /
        // polarity / scan-range filters once per X candidate (which
        // dominated long variable-query runtimes).
        let start_state = narrowed.clone();
        let result = match process_query_prepared_from(&concrete_val, start_state) {
            Ok(r) => r,
            Err(_) => continue, // skip candidates that error (e.g. Y still unbound)
        };

        // Merge into combined, deduping by (scan, floor(X)).
        let truncated_x = candidate.trunc() as i64;
        columns_present = result.columns_present; // last-wins; all concrete queries share a shape
        columns_present.comment = true;
        for mut row in result.rows {
            row.comment = Some(candidate);
            if let Some(scan) = row.scan {
                combined.entry((scan, Some(truncated_x))).or_insert(row);
            } else {
                combined
                    .entry((0, Some(truncated_x.wrapping_add(combined.len() as i64))))
                    .or_insert(row);
            }
        }
    }

    Ok(Some(crate::QueryResult {
        rows: combined.into_values().collect(),
        columns_present,
    }))
}

fn analyze_conditions(conds: &[Value]) -> VarProps {
    let mut p = VarProps::new();

    for c in conds {
        let ctype = c.get("type").and_then(|v| v.as_str()).unwrap_or("");
        if ctype == "xcondition" {
            if let (Some(min), Some(max)) = (
                c.get("min").and_then(|v| v.as_f64()),
                c.get("max").and_then(|v| v.as_f64()),
            ) {
                p.min = min;
                p.max = max;
            }
            if let (Some(mind), Some(maxd)) = (
                c.get("mindefect").and_then(|v| v.as_f64()),
                c.get("maxdefect").and_then(|v| v.as_f64()),
            ) {
                p.mindefect = mind;
                p.maxdefect = maxd;
            }
            continue;
        }

        if let Some(values) = c.get("value").and_then(|v| v.as_array()) {
            for v in values {
                if let Some(s) = v.as_str() {
                    if !s.contains('X') {
                        continue;
                    }
                    // This condition uses X — flag which peak column
                    // we should draw candidate X values from.
                    if s == "X" {
                        match ctype {
                            "ms1mzcondition" => p.query_ms1 = true,
                            "ms2productcondition" | "ms2neutrallosscondition" => p.query_ms2 = true,
                            "ms2precursorcondition" => p.query_ms2prec = true,
                            _ => {}
                        }
                    }
                    p.has_variable = true;

                    // Track smallest tolerance across all
                    // X-containing conditions (used to dedupe).
                    if let Some(q) = c.get("qualifiers") {
                        if let Some(ppm) = q.get("qualifierppmtolerance").and_then(|q| q["value"].as_f64()) {
                            p.ppm_tolerance = p.ppm_tolerance.min(ppm);
                        }
                        if let Some(da) = q.get("qualifiermztolerance").and_then(|q| q["value"].as_f64()) {
                            p.da_tolerance = p.da_tolerance.min(da);
                        }
                    }
                }
            }
        }

        // MOBILITY / xcondition-style conditions with variable min/max.
        for key in ["min", "max"] {
            if let Some(s) = c.get(key).and_then(|v| v.as_str()) {
                if s.contains('X') {
                    p.has_variable = true;
                }
            }
        }
    }

    p
}

fn has_variable_in_condition(c: &Value) -> bool {
    if c.get("type").and_then(|v| v.as_str()) == Some("xcondition") {
        return true;
    }
    if let Some(values) = c.get("value").and_then(|v| v.as_array()) {
        for v in values {
            if let Some(s) = v.as_str() {
                if s.contains('X') || s.contains('Y') {
                    return true;
                }
            }
        }
    }
    for key in ["min", "max"] {
        if let Some(s) = c.get(key).and_then(|v| v.as_str()) {
            if s.contains('X') || s.contains('Y') {
                return true;
            }
        }
    }
    false
}

/// Apply every X-binding MS1MZ condition's intensity qualifier to
/// narrow the candidate peak set in `state.ms1`. Mirrors the
/// `variable_x_ms1_df = ms1_df[intensity_mask]` loop in
/// `_evalute_variable_query`.
///
/// Only MS1MZ conditions are in scope — Python does this exclusively
/// for `ms1mzcondition` and leaves MS2 candidate pools untouched.
fn apply_variable_intensity_prefilter(conds: &[Value], state: &mut crate::Filtered) {
    for c in conds {
        if c.get("conditiontype") != Some(&Value::String("where".into())) {
            continue;
        }
        if c.get("type").and_then(|v| v.as_str()) != Some("ms1mzcondition") {
            continue;
        }
        let has_x = c
            .get("value")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .any(|v| v.as_str().map(|s| s.contains('X')).unwrap_or(false))
            })
            .unwrap_or(false);
        if !has_x {
            continue;
        }
        let q = c.get("qualifiers");
        let pred = crate::IntensityPredicate::from_qualifier(q);
        state
            .ms1
            .retain(|p| pred.matches(p.i, p.i_norm, p.i_tic_norm));
    }
}

fn collect_candidates(props: &VarProps, state: &crate::Filtered) -> Vec<f64> {
    let mut raw: Vec<f64> = Vec::new();
    if props.query_ms1 {
        raw.extend(state.ms1.iter().map(|p| p.mz));
    }
    if props.query_ms2 {
        raw.extend(state.ms2.iter().map(|p| p.mz));
    }
    if props.query_ms2prec {
        raw.extend(state.ms2.iter().map(|p| p.precmz));
    }
    if raw.is_empty() {
        return Vec::new();
    }
    // Sort + greedy dedupe mirroring Python's `running_max_mz` logic.
    // Python treats tolerances >= 10000 as sentinels ("unspecified")
    // and falls back to a 0.05 Da half-delta — see
    // `_determine_mz_max` in msql_engine.py.
    let ppm = if props.ppm_tolerance < 10000.0 { props.ppm_tolerance } else { 0.0 };
    let da = if props.da_tolerance < 10000.0 { props.da_tolerance } else { 0.0 };

    raw.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let mut out: Vec<f64> = Vec::with_capacity(raw.len() / 4);
    let mut running_max = f64::NEG_INFINITY;
    for mz in raw {
        if mz <= running_max {
            continue;
        }
        let raw_half = (mz * ppm / 1_000_000.0).max(da) / 2.0;
        let half_delta = if raw_half > 0.0 { raw_half } else { 0.05 };
        running_max = mz + half_delta;
        out.push(mz);
    }
    out
}

fn substitute_conditions(conds: &[Value], x: f64) -> Vec<Value> {
    let mut env = HashMap::new();
    env.insert("X".to_string(), x);

    conds
        .iter()
        .map(|c| substitute_one(c, &env))
        .filter(|c| !is_xcondition(c))
        .collect()
}

fn is_xcondition(c: &Value) -> bool {
    c.get("type").and_then(|v| v.as_str()) == Some("xcondition")
}

fn substitute_one(c: &Value, env: &HashMap<String, f64>) -> Value {
    let mut c = c.clone();
    let map = match c.as_object_mut() {
        Some(m) => m,
        None => return c,
    };

    // value[]
    if let Some(arr) = map.get_mut("value").and_then(|v| v.as_array_mut()) {
        for v in arr.iter_mut() {
            if let Some(s) = v.as_str() {
                let replaced = expr::substitute(s, env);
                // If the substitution collapsed to a pure number,
                // emit as JSON number; otherwise keep as string.
                if let Ok(n) = replaced.parse::<f64>() {
                    *v = json!(n);
                } else {
                    *v = Value::String(replaced);
                }
            }
        }
    }
    // min/max (mobility/xcondition)
    for key in ["min", "max"] {
        if let Some(val) = map.get_mut(key) {
            if let Some(s) = val.as_str() {
                let replaced = expr::substitute(s, env);
                if let Ok(n) = replaced.parse::<f64>() {
                    *val = json!(n);
                } else {
                    *val = Value::String(replaced);
                }
            }
        }
    }
    // qualifiers[*].value (e.g. INTENSITYMATCH=Y*0.5 still contains Y)
    if let Some(quals) = map.get_mut("qualifiers").and_then(|v| v.as_object_mut()) {
        for (_, q) in quals.iter_mut() {
            if let Some(qm) = q.as_object_mut() {
                if let Some(v) = qm.get_mut("value") {
                    if let Some(s) = v.as_str() {
                        let replaced = expr::substitute(s, env);
                        if let Ok(n) = replaced.parse::<f64>() {
                            *v = json!(n);
                        } else {
                            *v = Value::String(replaced);
                        }
                    }
                }
            }
        }
    }

    Value::Object(map.clone())
}

/// Unused for now but kept for the day we need scan-set accumulation
/// across candidates (e.g. for the collating step).
#[allow(dead_code)]
pub(crate) fn scan_union<'a>(
    iter: impl Iterator<Item = &'a crate::result::ResultRow>,
) -> BTreeSet<u32> {
    iter.filter_map(|r| r.scan).collect()
}
