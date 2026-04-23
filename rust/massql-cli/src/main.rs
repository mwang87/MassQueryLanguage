//! Rust port of `massql/msql_cmd.py`.
//!
//! Runs a single MassQL query against a mass-spec file and writes
//! TSV (or CSV) results. Column output matches the Python CLI:
//! populated columns + `filename` + `query_index`, sorted
//! alphabetically. Integer-typed columns (`scan`, `ms1scan`, `charge`,
//! `mslevel`) are written without trailing `.0`.

use std::fs::File;
use std::io::{BufWriter, Write};
use std::path::PathBuf;
use std::process::ExitCode;

use std::collections::BTreeSet;

use clap::Parser;
use massql_engine::process_query;
use massql_engine::result::{ColumnSet, QueryResult, ResultRow};
use massql_loader::{export_mgf, export_mzml, extract_scans, load_file, ExtractedSpectrum};

#[derive(Parser, Debug)]
#[command(name = "massql", about = "MassQL — Rust port")]
struct Args {
    /// Input mass-spec file (mzML currently; others TBD)
    filename: PathBuf,

    /// MassQL query (required unless `--query-yaml` is given).
    query: Option<String>,

    /// Read the MassQL query from the `query:` field of a YAML file
    /// instead of the positional argument. Mutually exclusive with
    /// the positional `<QUERY>`.
    #[arg(long, conflicts_with = "query")]
    query_yaml: Option<PathBuf>,

    /// Output TSV file (.tsv) or CSV (.csv) path. `.tsv` uses tab
    /// separator, otherwise comma.
    #[arg(long)]
    output_file: Option<PathBuf>,

    /// Re-read the input file, pull out every spectrum that matched
    /// the query, and write one JSON object per line to this path.
    /// Each object mirrors Python's `--extract_json`:
    /// `{peaks, mslevel, scan, precursor_mz?, new_scan, query_results}`.
    #[arg(long)]
    extract_json: Option<PathBuf>,

    /// Write matched spectra as a `.mgf` file (BEGIN IONS / PEPMASS /
    /// SCANS / peaks / END IONS), mirroring Python's `_export_mgf`.
    #[arg(long)]
    extract_mgf: Option<PathBuf>,

    /// Write matched spectra as a `.mzML` file, mirroring Python's
    /// `_export_mzML`.
    #[arg(long)]
    extract_mzml: Option<PathBuf>,

    /// Print a natural-language explanation of the query to stdout
    /// and exit without running it. Equivalent to calling
    /// `massql_translator::translate_query(query, Lang::English)`.
    #[arg(long)]
    translate: bool,
}

/// Narrow shape of what we pull out of the YAML file — we only care
/// about the `query` key, but we allow unknown siblings so callers
/// can pile whatever else they want in the file alongside it.
#[derive(serde::Deserialize)]
struct QueryYaml {
    query: String,
}

fn resolve_query(args: &Args) -> Result<String, String> {
    if let Some(q) = &args.query {
        return Ok(q.clone());
    }
    if let Some(path) = &args.query_yaml {
        let text = std::fs::read_to_string(path)
            .map_err(|e| format!("read {}: {}", path.display(), e))?;
        let parsed: QueryYaml = serde_yaml::from_str(&text)
            .map_err(|e| format!("parse {} as YAML: {}", path.display(), e))?;
        return Ok(parsed.query);
    }
    Err("missing query: pass <QUERY> positionally or --query-yaml PATH".into())
}

fn main() -> ExitCode {
    let args = Args::parse();

    let query = match resolve_query(&args) {
        Ok(q) => q,
        Err(e) => {
            eprintln!("{}", e);
            return ExitCode::from(2);
        }
    };

    if args.translate {
        match massql_translator::translate_query(&query, massql_translator::Lang::English) {
            Ok(s) => {
                println!("{}", s);
                return ExitCode::SUCCESS;
            }
            Err(e) => {
                eprintln!("translate error: {}", e);
                return ExitCode::from(6);
            }
        }
    }

    let dataset = match load_file(&args.filename) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("load error: {}", e);
            return ExitCode::from(2);
        }
    };

    let result = match process_query(&query, &dataset) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("query error: {}", e);
            return ExitCode::from(3);
        }
    };

    eprintln!("#############################");
    eprintln!("MassQL Found {} results", result.rows.len());
    eprintln!("#############################");

    if let Some(out) = &args.output_file {
        let sep = if out
            .extension()
            .and_then(|e| e.to_str())
            .map(|s| s.eq_ignore_ascii_case("tsv"))
            .unwrap_or(false)
        {
            '\t'
        } else {
            ','
        };

        let filename = args
            .filename
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_string();

        if !result.rows.is_empty() {
            if let Err(e) = write_table(out, sep, &result, &filename, 0) {
                eprintln!("write error: {}", e);
                return ExitCode::from(4);
            }
        }
    }

    if !result.rows.is_empty()
        && (args.extract_json.is_some()
            || args.extract_mgf.is_some()
            || args.extract_mzml.is_some())
    {
        let filename_short = args
            .filename
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_string();
        let scans: BTreeSet<u32> = result.rows.iter().filter_map(|r| r.scan).collect();
        let spectra = match extract_scans(&args.filename, &scans) {
            Ok(s) => s,
            Err(e) => {
                eprintln!("extract error: {}", e);
                return ExitCode::from(5);
            }
        };
        let new_scans: Vec<u32> = (1..=spectra.len() as u32).collect();
        eprintln!("Extracting {} spectra", spectra.len());

        if let Some(p) = &args.extract_json {
            if let Err(e) = write_extract_json(p, &spectra, &new_scans, &result, &filename_short, 0) {
                eprintln!("extract-json error: {}", e);
                return ExitCode::from(5);
            }
        }
        if let Some(p) = &args.extract_mgf {
            if let Err(e) = export_mgf(p, &spectra, &new_scans) {
                eprintln!("extract-mgf error: {}", e);
                return ExitCode::from(5);
            }
        }
        if let Some(p) = &args.extract_mzml {
            if let Err(e) = export_mzml(p, &spectra, &new_scans) {
                eprintln!("extract-mzml error: {}", e);
                return ExitCode::from(5);
            }
        }
    }

    ExitCode::SUCCESS
}

/// Mirror of `_extract_spectra(..., output_json_filename=...)`. One
/// JSON object per line, keyed by `{peaks, mslevel, scan,
/// precursor_mz?, new_scan, query_results}`. `query_results` is the
/// full sorted-column row dict for every result row that referenced
/// this scan, including the synthetic `filename` / `query_index` /
/// `new_scan` fields the CLI adds.
fn write_extract_json(
    out: &PathBuf,
    spectra: &[ExtractedSpectrum],
    new_scans: &[u32],
    result: &QueryResult,
    filename: &str,
    query_index: u32,
) -> std::io::Result<()> {
    let file = File::create(out)?;
    let mut w = BufWriter::new(file);

    for (spec, &new_scan) in spectra.iter().zip(new_scans.iter()) {
        let matching_rows: Vec<&ResultRow> = result
            .rows
            .iter()
            .filter(|r| r.scan.map(|s| s.to_string()).as_deref() == Some(spec.scan.as_str()))
            .collect();

        write_spectrum_json(
            &mut w,
            spec,
            new_scan,
            &matching_rows,
            result,
            filename,
            query_index,
        )?;
    }
    w.flush()?;
    Ok(())
}

/// Writes one JSON object per spectrum, matching Python's key order
/// (which is insertion order via `dict`: peaks, mslevel, scan,
/// precursor_mz, new_scan, query_results). We mirror that so someone
/// diffing the two outputs line-by-line sees matching structure.
fn write_spectrum_json(
    w: &mut impl Write,
    spec: &ExtractedSpectrum,
    new_scan: u32,
    rows: &[&ResultRow],
    result: &QueryResult,
    filename: &str,
    query_index: u32,
) -> std::io::Result<()> {
    write!(w, "{{\"peaks\": [")?;
    for (i, &(mz, intensity)) in spec.peaks.iter().enumerate() {
        if i > 0 {
            write!(w, ", ")?;
        }
        write!(
            w,
            "[{}, {}]",
            format_py_float(mz),
            format_py_float(intensity as f64)
        )?;
    }
    write!(w, "], \"mslevel\": {}", spec.mslevel)?;
    write!(w, ", \"scan\": \"{}\"", spec.scan)?;
    if let Some(pm) = spec.precursor_mz {
        write!(w, ", \"precursor_mz\": {}", format_py_float(pm))?;
    }
    write!(w, ", \"new_scan\": {}", new_scan)?;

    write!(w, ", \"query_results\": [")?;
    for (i, row) in rows.iter().enumerate() {
        if i > 0 {
            write!(w, ", ")?;
        }
        write_query_result_dict(w, row, result, new_scan, filename, query_index)?;
    }
    writeln!(w, "]}}")?;
    Ok(())
}

/// Serialize a single `ResultRow` as the dict Python's
/// `filtered_by_scan_df.to_dict(orient="records")` produces. Columns
/// come out in their DataFrame insertion order; for parity we mirror
/// Python's column emission order rather than the alphabetically-
/// sorted CLI TSV order.
fn write_query_result_dict(
    w: &mut impl Write,
    row: &ResultRow,
    result: &QueryResult,
    new_scan: u32,
    filename: &str,
    query_index: u32,
) -> std::io::Result<()> {
    let cs = &result.columns_present;
    write!(w, "{{")?;
    let mut first = true;
    let comma = |w: &mut dyn Write, first: &mut bool| -> std::io::Result<()> {
        if !*first {
            write!(w, ", ")?;
        }
        *first = false;
        Ok(())
    };
    if cs.scan {
        comma(w, &mut first)?;
        write!(w, "\"scan\": {}", row.scan.unwrap_or(0))?;
    }
    if cs.precmz {
        comma(w, &mut first)?;
        write!(w, "\"precmz\": ")?;
        write_json_float(w, row.precmz)?;
    }
    if cs.ms1scan {
        comma(w, &mut first)?;
        write!(w, "\"ms1scan\": {}", row.ms1scan.unwrap_or(0))?;
    }
    if cs.rt {
        comma(w, &mut first)?;
        write!(w, "\"rt\": ")?;
        write_json_float(w, row.rt)?;
    }
    if cs.charge {
        comma(w, &mut first)?;
        write!(w, "\"charge\": {}", row.charge.unwrap_or(0))?;
    }
    if cs.comment {
        comma(w, &mut first)?;
        // Python stores the variable-query comment as a string
        // (`str(mz_val)` in `_evalute_variable_query`) and carries it
        // through as-is in query_results. Match that.
        write!(w, "\"comment\": ")?;
        match row.comment {
            Some(c) => write!(w, "\"{}\"", format_py_float(c))?,
            None => write!(w, "NaN")?,
        }
    }
    if cs.i {
        comma(w, &mut first)?;
        write!(w, "\"i\": ")?;
        write_json_float(w, row.i)?;
    }
    if cs.i_norm {
        comma(w, &mut first)?;
        write!(w, "\"i_norm\": ")?;
        write_json_float(w, row.i_norm)?;
    }
    if cs.mslevel {
        comma(w, &mut first)?;
        write!(w, "\"mslevel\": {}", row.mslevel.unwrap_or(0))?;
    }
    if cs.i_norm_ms1 {
        comma(w, &mut first)?;
        write!(w, "\"i_norm_ms1\": ")?;
        write_json_float(w, row.i_norm_ms1)?;
    }
    if cs.mz {
        comma(w, &mut first)?;
        write!(w, "\"mz\": ")?;
        write_json_float(w, row.mz)?;
    }
    if cs.mz_defect {
        comma(w, &mut first)?;
        write!(w, "\"mz_defect\": ")?;
        write_json_float(w, row.mz_defect)?;
    }
    if cs.polarity {
        comma(w, &mut first)?;
        write!(w, "\"polarity\": {}", row.polarity.unwrap_or(0))?;
    }
    if cs.i_tic_norm {
        comma(w, &mut first)?;
        write!(w, "\"i_tic_norm\": ")?;
        write_json_float(w, row.i_tic_norm)?;
    }
    if cs.mobility {
        comma(w, &mut first)?;
        write!(w, "\"mobility\": ")?;
        write_json_float(w, row.mobility)?;
    }
    // CLI-synthesized columns. Python's order is:
    //   query_index, mz_lower, mz_upper, filename, new_scan
    // (see msql_cmd.py — mz_lower/mz_upper are added after
    // type-coercion, filename after that, new_scan last via
    // _extract_spectra). Match it for byte-equivalent output.
    comma(w, &mut first)?;
    write!(w, "\"query_index\": {}", query_index)?;
    if cs.comment {
        comma(w, &mut first)?;
        write!(w, "\"mz_lower\": ")?;
        write_json_float(w, row.comment.map(|c| c - 10.0))?;
        comma(w, &mut first)?;
        write!(w, "\"mz_upper\": ")?;
        write_json_float(w, row.comment.map(|c| c + 10.0))?;
    }
    comma(w, &mut first)?;
    write!(w, "\"filename\": {:?}", filename)?;
    comma(w, &mut first)?;
    write!(w, "\"new_scan\": {}", new_scan)?;
    write!(w, "}}")?;
    Ok(())
}

fn write_json_float(w: &mut impl Write, v: Option<f64>) -> std::io::Result<()> {
    match v {
        Some(x) => write!(w, "{}", format_py_float(x)),
        None => write!(w, "NaN"),
    }
}

/// Mirrors the Python CLI's TSV writer:
///
///   * adds `filename` + `query_index` columns
///   * sorts column names alphabetically
///   * emits integer columns (`scan`, `ms1scan`, `charge`, `mslevel`)
///     without a trailing `.0`
///   * uses Python-compatible float formatting for everything else
fn write_table(
    path: &PathBuf,
    sep: char,
    result: &QueryResult,
    filename: &str,
    query_index: u32,
) -> std::io::Result<()> {
    let mut columns = populated_columns(&result.columns_present);
    columns.push(Column::Filename);
    columns.push(Column::QueryIndex);
    columns.sort_by_key(|c| c.header());

    let file = File::create(path)?;
    let mut w = BufWriter::new(file);

    // Header
    for (i, c) in columns.iter().enumerate() {
        if i > 0 {
            write!(w, "{}", sep)?;
        }
        write!(w, "{}", c.header())?;
    }
    writeln!(w)?;

    for row in &result.rows {
        for (i, c) in columns.iter().enumerate() {
            if i > 0 {
                write!(w, "{}", sep)?;
            }
            c.write(&mut w, row, filename, query_index)?;
        }
        writeln!(w)?;
    }
    w.flush()?;
    Ok(())
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Column {
    Scan,
    Ms1Scan,
    Rt,
    Precmz,
    Mz,
    Charge,
    Polarity,
    Mslevel,
    I,
    INorm,
    ITicNorm,
    INormMs1,
    Mobility,
    MzDefect,
    Comment,
    MzLower,
    MzUpper,
    Filename,
    QueryIndex,
}

impl Column {
    fn header(&self) -> &'static str {
        match self {
            Column::Scan => "scan",
            Column::Ms1Scan => "ms1scan",
            Column::Rt => "rt",
            Column::Precmz => "precmz",
            Column::Mz => "mz",
            Column::Charge => "charge",
            Column::Polarity => "polarity",
            Column::Mslevel => "mslevel",
            Column::I => "i",
            Column::INorm => "i_norm",
            Column::ITicNorm => "i_tic_norm",
            Column::INormMs1 => "i_norm_ms1",
            Column::Mobility => "mobility",
            Column::MzDefect => "mz_defect",
            Column::Comment => "comment",
            Column::MzLower => "mz_lower",
            Column::MzUpper => "mz_upper",
            Column::Filename => "filename",
            Column::QueryIndex => "query_index",
        }
    }

    fn write(
        &self,
        w: &mut impl Write,
        row: &ResultRow,
        filename: &str,
        query_index: u32,
    ) -> std::io::Result<()> {
        match self {
            Column::Scan => write_int(w, row.scan),
            Column::Ms1Scan => write_int(w, row.ms1scan),
            Column::Rt => write_float(w, row.rt),
            Column::Precmz => write_float(w, row.precmz),
            Column::Mz => write_float(w, row.mz),
            Column::Charge => write_int(w, row.charge),
            Column::Polarity => write_int(w, row.polarity),
            Column::Mslevel => write_int(w, row.mslevel),
            Column::I => write_float(w, row.i),
            Column::INorm => write_float(w, row.i_norm),
            Column::ITicNorm => write_float(w, row.i_tic_norm),
            Column::INormMs1 => write_float(w, row.i_norm_ms1),
            Column::Mobility => write_float(w, row.mobility),
            Column::MzDefect => write_float(w, row.mz_defect),
            Column::Comment => write_float(w, row.comment),
            Column::MzLower => write_float(w, row.comment.map(|c| c - 10.0)),
            Column::MzUpper => write_float(w, row.comment.map(|c| c + 10.0)),
            Column::Filename => write!(w, "{}", filename),
            Column::QueryIndex => write!(w, "{}", query_index),
        }
    }
}

fn populated_columns(cs: &ColumnSet) -> Vec<Column> {
    let mut out = Vec::new();
    if cs.scan {
        out.push(Column::Scan);
    }
    if cs.ms1scan {
        out.push(Column::Ms1Scan);
    }
    if cs.rt {
        out.push(Column::Rt);
    }
    if cs.precmz {
        out.push(Column::Precmz);
    }
    if cs.mz {
        out.push(Column::Mz);
    }
    if cs.charge {
        out.push(Column::Charge);
    }
    if cs.polarity {
        out.push(Column::Polarity);
    }
    if cs.mslevel {
        out.push(Column::Mslevel);
    }
    if cs.i {
        out.push(Column::I);
    }
    if cs.i_norm {
        out.push(Column::INorm);
    }
    if cs.i_tic_norm {
        out.push(Column::ITicNorm);
    }
    if cs.i_norm_ms1 {
        out.push(Column::INormMs1);
    }
    if cs.mobility {
        out.push(Column::Mobility);
    }
    if cs.mz_defect {
        out.push(Column::MzDefect);
    }
    if cs.comment {
        out.push(Column::Comment);
        // mz_lower / mz_upper are always emitted alongside comment —
        // Python's CLI derives them unconditionally from comment.
        out.push(Column::MzLower);
        out.push(Column::MzUpper);
    }
    out
}

fn write_int<T: std::fmt::Display>(w: &mut impl Write, v: Option<T>) -> std::io::Result<()> {
    match v {
        Some(x) => write!(w, "{}", x),
        None => Ok(()), // empty field = NaN in pandas TSV
    }
}

fn write_float(w: &mut impl Write, v: Option<f64>) -> std::io::Result<()> {
    match v {
        Some(x) => write!(w, "{}", format_py_float(x)),
        None => Ok(()),
    }
}

/// Python-compatible formatting. We reach into `massql_parser::py_float`
/// indirectly via its public `parse_msql` — actually keep a local copy
/// since the parser's version is `pub(crate)`. Simpler to inline the
/// same rules here.
fn format_py_float(x: f64) -> String {
    if x.is_nan() {
        return "".into(); // pandas writes empty for NaN
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    if x == 0.0 {
        return "0.0".into();
    }
    // Shortest round-trip via ryu, then reshape to Python's
    // `str(float)` rules (scientific when abs<1e-4 or >=1e16).
    let abs = x.abs();
    let use_sci = abs < 1e-4 || abs >= 1e16;

    let mut buf = ryu::Buffer::new();
    let s = buf.format(x);

    if !use_sci {
        if s.contains('e') {
            // ryu chose sci when Python wouldn't — fall back.
            return format!("{}", x);
        }
        return if s.contains('.') {
            s.to_string()
        } else {
            format!("{}.0", s)
        };
    }
    // Scientific: Python-style "Ne±MM"
    let negative = x.is_sign_negative();
    let s = if negative { &s[1..] } else { s };
    let (mantissa, exp): (&str, i32) = if let Some(i) = s.find('e') {
        (&s[..i], s[i + 1..].parse().unwrap_or(0))
    } else {
        // Fixed-form from ryu but Python wants sci — rare; bail.
        return format!("{}", x);
    };
    let mant = if mantissa.ends_with(".0") {
        &mantissa[..mantissa.len() - 2]
    } else {
        mantissa
    };
    let sign_ch = if negative { "-" } else { "" };
    let exp_sign = if exp < 0 { '-' } else { '+' };
    format!("{}{}e{}{:02}", sign_ch, mant, exp_sign, exp.abs())
}
