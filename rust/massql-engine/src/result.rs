//! Result collation — mirrors `_executecollate_query` in the Python
//! engine. Produces a [`QueryResult`] containing typed rows plus an
//! inventory of columns to emit (order-insensitive here; the CLI
//! sorts them alphabetically on write, matching Python).

use std::collections::BTreeMap;

use massql_loader::{Ms1Peak, Ms2Peak};
use serde_json::Value;

use crate::{EngineError, Filtered};

/// One row of engine output. Every column is represented; callers use
/// the `columns_present` field on [`QueryResult`] to know which are
/// populated and which should be omitted from TSV output.
#[derive(Debug, Clone, Default)]
pub struct ResultRow {
    pub scan: Option<u32>,
    pub ms1scan: Option<u32>,
    pub rt: Option<f64>,
    pub precmz: Option<f64>,
    pub mz: Option<f64>,
    pub charge: Option<i32>,
    pub polarity: Option<u8>,
    pub mslevel: Option<u8>,
    pub i: Option<f64>,
    pub i_norm: Option<f64>,
    pub i_tic_norm: Option<f64>,
    /// MS1-side intensity normalization, joined in for MS2 scaninfo
    /// results (Python's `i_norm_ms1` column).
    pub i_norm_ms1: Option<f64>,
    pub mobility: Option<f64>,
    /// The concrete X value used when running a variable query.
    /// Python's CLI surfaces this as a `comment` column (plus
    /// `mz_lower` / `mz_upper` = comment ± 10).
    pub comment: Option<f64>,
    /// Fractional part of `mz` — populated only when a FILTER clause
    /// applied a MASSDEFECT qualifier (mirrors the pandas column leak
    /// in `msql_engine_filters.py::ms1_filter`).
    pub mz_defect: Option<f64>,
}

#[derive(Debug, Clone, Default)]
pub struct QueryResult {
    pub rows: Vec<ResultRow>,
    /// The Python pipeline emits only the columns that are populated.
    /// We track this per-result so the CLI output matches pandas'
    /// behavior (e.g. no `precmz` column for an MS1 query).
    pub columns_present: ColumnSet,
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct ColumnSet {
    pub scan: bool,
    pub ms1scan: bool,
    pub rt: bool,
    pub precmz: bool,
    pub mz: bool,
    pub charge: bool,
    pub polarity: bool,
    pub mslevel: bool,
    pub i: bool,
    pub i_norm: bool,
    pub i_tic_norm: bool,
    pub i_norm_ms1: bool,
    pub mobility: bool,
    pub comment: bool,
    pub mz_defect: bool,
}

/// Dispatch on query function + datatype.
pub fn collate(querytype: &Value, state: &Filtered) -> Result<QueryResult, EngineError> {
    let function = querytype.get("function").and_then(|v| v.as_str());
    let datatype = querytype.get("datatype").and_then(|v| v.as_str()).unwrap_or("");

    let mut out = match function {
        None => pass_through(datatype, state),
        Some("functionscaninfo") => scaninfo(datatype, state),
        Some("functionscansum") => scansum(datatype, state),
        Some("functionscannum") => scannum(datatype, state),
        Some("functionscanmz") => scanmz(datatype, state),
        Some(other) => Err(EngineError::Semantic(format!(
            "unsupported query function: {}",
            other
        ))),
    }?;

    // If the FILTER path touched MASSDEFECT, emit the `mz_defect`
    // column that Python leaks from the filter step. Computed from
    // whatever `mz` the collation preserved (scansum/pass-through).
    if state.mz_defect_column {
        out.columns_present.mz_defect = true;
        for row in &mut out.rows {
            if let Some(mz) = row.mz {
                row.mz_defect = Some(mz - mz.floor());
            }
        }
    }
    Ok(out)
}

// --------------- No function: return raw filtered rows ---------------

fn pass_through(datatype: &str, state: &Filtered) -> Result<QueryResult, EngineError> {
    let (rows, cols) = match datatype {
        "datams1data" => (state.ms1.iter().map(ms1_row).collect(), ms1_cols()),
        "datams2data" => (state.ms2.iter().map(ms2_row).collect(), ms2_cols()),
        _ => {
            return Err(EngineError::Semantic(format!(
                "unsupported datatype: {}",
                datatype
            )));
        }
    };
    Ok(QueryResult { rows, columns_present: cols })
}

// --------------- scaninfo: one row per scan, aggregated ---------------

fn scaninfo(datatype: &str, state: &Filtered) -> Result<QueryResult, EngineError> {
    match datatype {
        "datams1data" => Ok(scaninfo_ms1(state)),
        "datams2data" => Ok(scaninfo_ms2(state)),
        _ => Err(EngineError::Semantic(format!(
            "unsupported datatype for scaninfo: {}",
            datatype
        ))),
    }
}

fn scaninfo_ms1(state: &Filtered) -> QueryResult {
    // Python: groupby("scan"), first() for scan+rt, sum() for i,
    // max() for i_norm, mslevel=1.
    let mut bucket: BTreeMap<u32, (f64, f64, f64)> = BTreeMap::new();
    // (rt_of_first, i_sum, i_norm_max)
    for p in &state.ms1 {
        let entry = bucket.entry(p.scan).or_insert((p.rt, 0.0, 0.0));
        entry.1 += p.i as f64;
        entry.2 = entry.2.max(p.i_norm as f64);
    }
    let rows: Vec<ResultRow> = bucket
        .into_iter()
        .map(|(scan, (rt, i_sum, i_norm_max))| ResultRow {
            scan: Some(scan),
            rt: Some(rt),
            mslevel: Some(1),
            i: Some(i_sum),
            i_norm: Some(i_norm_max),
            ..Default::default()
        })
        .collect();

    QueryResult {
        rows,
        columns_present: ColumnSet {
            scan: true,
            rt: true,
            mslevel: true,
            i: true,
            i_norm: true,
            ..Default::default()
        },
    }
}

fn scaninfo_ms2(state: &Filtered) -> QueryResult {
    // Aggregate MS2 by scan.
    #[derive(Default)]
    struct Agg {
        rt: f64,
        precmz: f64,
        ms1scan: u32,
        charge: i32,
        i_sum: f64,
        i_norm_max: f64,
        mobility: Option<f64>,
        seen: bool,
    }
    let mut bucket: BTreeMap<u32, Agg> = BTreeMap::new();
    for p in &state.ms2 {
        let entry = bucket.entry(p.scan).or_default();
        if !entry.seen {
            entry.rt = p.rt;
            entry.precmz = p.precmz;
            entry.ms1scan = p.ms1scan;
            entry.charge = p.charge;
            entry.mobility = p.mobility;
            entry.seen = true;
        }
        entry.i_sum += p.i as f64;
        entry.i_norm_max = entry.i_norm_max.max(p.i_norm as f64);
    }

    // i_norm_ms1: for each scan's ms1scan, take the max i_norm over
    // that MS1 scan (from the *filtered* MS1 — matches Python's
    // `ms1_df.groupby("scan").max()`).
    let mut ms1_norm: BTreeMap<u32, f64> = BTreeMap::new();
    for p in &state.ms1 {
        let entry = ms1_norm.entry(p.scan).or_insert(0.0);
        if (p.i_norm as f64) > *entry {
            *entry = p.i_norm as f64;
        }
    }

    let has_mobility = state.ms2.iter().any(|p| p.mobility.is_some());

    let rows: Vec<ResultRow> = bucket
        .into_iter()
        .map(|(scan, a)| ResultRow {
            scan: Some(scan),
            rt: Some(a.rt),
            precmz: Some(a.precmz),
            ms1scan: Some(a.ms1scan),
            charge: Some(a.charge),
            mslevel: Some(2),
            i: Some(a.i_sum),
            i_norm: Some(a.i_norm_max),
            i_norm_ms1: ms1_norm.get(&a.ms1scan).copied(),
            mobility: if has_mobility { a.mobility } else { None },
            ..Default::default()
        })
        .collect();

    QueryResult {
        rows,
        columns_present: ColumnSet {
            scan: true,
            rt: true,
            precmz: true,
            ms1scan: true,
            charge: true,
            mslevel: true,
            i: true,
            i_norm: true,
            i_norm_ms1: true,
            mobility: has_mobility,
            ..Default::default()
        },
    }
}

// --------------- scansum: groupby scan, sum i, first() other cols ---

fn scansum(datatype: &str, state: &Filtered) -> Result<QueryResult, EngineError> {
    match datatype {
        "datams1data" => Ok(scansum_ms1(state)),
        "datams2data" => Ok(scansum_ms2(state)),
        _ => Err(EngineError::Semantic(format!(
            "unsupported datatype for scansum: {}",
            datatype
        ))),
    }
}

fn scansum_ms1(state: &Filtered) -> QueryResult {
    let mut bucket: BTreeMap<u32, (Ms1Peak, f64)> = BTreeMap::new();
    for p in &state.ms1 {
        let entry = bucket.entry(p.scan).or_insert((*p, 0.0));
        entry.1 += p.i as f64;
    }
    let rows: Vec<ResultRow> = bucket
        .into_values()
        .map(|(first, i_sum)| ResultRow {
            scan: Some(first.scan),
            rt: Some(first.rt),
            mz: Some(first.mz),
            polarity: Some(first.polarity),
            i: Some(i_sum),
            i_norm: Some(first.i_norm as f64),
            i_tic_norm: Some(first.i_tic_norm as f64),
            ..Default::default()
        })
        .collect();
    QueryResult {
        rows,
        columns_present: ms1_cols(),
    }
}

fn scansum_ms2(state: &Filtered) -> QueryResult {
    let mut bucket: BTreeMap<u32, (Ms2Peak, f64)> = BTreeMap::new();
    for p in &state.ms2 {
        let entry = bucket.entry(p.scan).or_insert((*p, 0.0));
        entry.1 += p.i as f64;
    }
    let rows: Vec<ResultRow> = bucket
        .into_values()
        .map(|(first, i_sum)| ResultRow {
            scan: Some(first.scan),
            ms1scan: Some(first.ms1scan),
            rt: Some(first.rt),
            precmz: Some(first.precmz),
            mz: Some(first.mz),
            charge: Some(first.charge),
            polarity: Some(first.polarity),
            i: Some(i_sum),
            i_norm: Some(first.i_norm as f64),
            i_tic_norm: Some(first.i_tic_norm as f64),
            mobility: first.mobility,
            ..Default::default()
        })
        .collect();
    QueryResult {
        rows,
        columns_present: ms2_cols(),
    }
}

// --------------- scannum: one column, distinct scans ---

fn scannum(datatype: &str, state: &Filtered) -> Result<QueryResult, EngineError> {
    let scans: std::collections::BTreeSet<u32> = match datatype {
        "datams1data" => state.ms1.iter().map(|p| p.scan).collect(),
        "datams2data" => state.ms2.iter().map(|p| p.scan).collect(),
        _ => {
            return Err(EngineError::Semantic(format!(
                "unsupported datatype for scannum: {}",
                datatype
            )))
        }
    };
    let rows: Vec<ResultRow> = scans
        .into_iter()
        .map(|s| ResultRow {
            scan: Some(s),
            ..Default::default()
        })
        .collect();
    Ok(QueryResult {
        rows,
        columns_present: ColumnSet {
            scan: true,
            ..Default::default()
        },
    })
}

// --------------- scanmz: distinct precursor m/z ---

fn scanmz(datatype: &str, state: &Filtered) -> Result<QueryResult, EngineError> {
    match datatype {
        "datams2data" => {
            let mut seen = std::collections::BTreeSet::new();
            let mut rows = Vec::new();
            for p in &state.ms2 {
                // BTreeSet doesn't accept f64 directly; use bit pattern.
                if seen.insert(p.precmz.to_bits()) {
                    rows.push(ResultRow {
                        precmz: Some(p.precmz),
                        ..Default::default()
                    });
                }
            }
            Ok(QueryResult {
                rows,
                columns_present: ColumnSet {
                    precmz: true,
                    ..Default::default()
                },
            })
        }
        _ => Err(EngineError::Semantic(
            "scanmz is only defined on MS2DATA".into(),
        )),
    }
}

// ==================== helpers ====================

fn ms1_row(p: &Ms1Peak) -> ResultRow {
    ResultRow {
        scan: Some(p.scan),
        rt: Some(p.rt),
        mz: Some(p.mz),
        polarity: Some(p.polarity),
        i: Some(p.i as f64),
        i_norm: Some(p.i_norm as f64),
        i_tic_norm: Some(p.i_tic_norm as f64),
        ..Default::default()
    }
}

fn ms2_row(p: &Ms2Peak) -> ResultRow {
    ResultRow {
        scan: Some(p.scan),
        ms1scan: Some(p.ms1scan),
        rt: Some(p.rt),
        precmz: Some(p.precmz),
        mz: Some(p.mz),
        charge: Some(p.charge),
        polarity: Some(p.polarity),
        i: Some(p.i as f64),
        i_norm: Some(p.i_norm as f64),
        i_tic_norm: Some(p.i_tic_norm as f64),
        mobility: p.mobility,
        ..Default::default()
    }
}

fn ms1_cols() -> ColumnSet {
    ColumnSet {
        scan: true,
        rt: true,
        mz: true,
        polarity: true,
        i: true,
        i_norm: true,
        i_tic_norm: true,
        ..Default::default()
    }
}

fn ms2_cols() -> ColumnSet {
    ColumnSet {
        scan: true,
        ms1scan: true,
        rt: true,
        precmz: true,
        mz: true,
        charge: true,
        polarity: true,
        i: true,
        i_norm: true,
        i_tic_norm: true,
        mobility: false, // turned on per-file below
        ..Default::default()
    }
}
