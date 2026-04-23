//! Rust port of `massql/msql_translator.py` — turns a parsed MassQL
//! query into a plain-language description.
//!
//! Scope: English only for now. The Python module supports nine
//! languages, but the structure (dispatch on condition type, glue
//! qualifiers in with a "with" clause) is identical; other languages
//! can be added mechanically by extending [`Lang`] and the string
//! tables. [`translate_query`] returns a `semantic` error for
//! languages we haven't wired up yet so callers can tell the
//! difference between "unsupported" and a silent English fallback.

use massql_parser::parse_msql;
use serde_json::Value;
use thiserror::Error;

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub enum Lang {
    #[default]
    English,
}

impl Lang {
    pub fn from_str(s: &str) -> Result<Lang, TranslateError> {
        match s.to_ascii_lowercase().as_str() {
            "english" | "en" => Ok(Lang::English),
            other => Err(TranslateError::UnsupportedLang(other.to_string())),
        }
    }
}

#[derive(Debug, Error)]
pub enum TranslateError {
    #[error("parse: {0}")]
    Parse(String),
    #[error("language {0:?} not supported in the Rust port (English only for now)")]
    UnsupportedLang(String),
    #[error("semantic: {0}")]
    Semantic(String),
}

/// Parse + translate in one step. Mirrors Python's `translate_query`.
pub fn translate_query(query: &str, lang: Lang) -> Result<String, TranslateError> {
    let parsed = parse_msql(query).map_err(|e| TranslateError::Parse(e.to_string()))?;
    translate_parsed(&parsed, lang)
}

/// Translate an already-parsed query value.
pub fn translate_parsed(parsed: &Value, lang: Lang) -> Result<String, TranslateError> {
    let mut sentences: Vec<String> = Vec::new();

    let querytype = parsed
        .get("querytype")
        .ok_or_else(|| TranslateError::Semantic("missing querytype".into()))?;
    sentences.push(translate_querytype(querytype, lang));

    let conditions = parsed
        .get("conditions")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    if !conditions.is_empty() {
        sentences.push(match lang {
            Lang::English => "The following conditions are applied to find scans in the mass spec data.".into(),
        });
    }
    for cond in &conditions {
        sentences.push(translate_condition(cond, lang));
    }
    Ok(sentences.join("\n"))
}

fn ms_level(querytype: &Value) -> &'static str {
    match querytype.get("datatype").and_then(|v| v.as_str()) {
        Some("datams2data") => "MS2",
        _ => "MS1",
    }
}

fn translate_querytype(querytype: &Value, lang: Lang) -> String {
    let level = ms_level(querytype);
    let function = querytype.get("function").and_then(|v| v.as_str());
    match (lang, function) {
        (Lang::English, Some("functionscaninfo")) => {
            format!("Returning the scan information on {}.", level)
        }
        (Lang::English, Some("functionscansum")) => {
            format!("Returning the summed scan on {}.", level)
        }
        (Lang::English, Some("functionscannum")) => {
            format!("Returning the scan numbers on {}.", level)
        }
        (Lang::English, Some("functionscanmz")) => {
            format!("Returning the m/z of each matching {} spectrum.", level)
        }
        (Lang::English, Some("functionscanmaxint")) => {
            format!("Returning the most intense peaks per {} scan.", level)
        }
        (Lang::English, Some("functionscanrangesum")) => {
            format!("Returning the summed intensity by m/z bin on {}.", level)
        }
        (Lang::English, None) => {
            format!("Returning all {} peak rows.", level)
        }
        (Lang::English, Some(other)) => {
            format!("Running function `{}` on {}.", other, level)
        }
    }
}

// ==================== conditions ====================

fn translate_condition(cond: &Value, lang: Lang) -> String {
    let qualifiers_part = cond
        .get("qualifiers")
        .map(|q| {
            let preposition = match lang {
                Lang::English => "with",
            };
            format!(" {} {}", preposition, translate_qualifiers(q, lang))
        })
        .unwrap_or_default();

    let ctype = cond.get("type").and_then(|v| v.as_str()).unwrap_or("");
    let values_str = || joined_values(cond);

    match ctype {
        "ms2productcondition" => match lang {
            Lang::English => format!(
                "Finding MS2 peak at m/z {}{}.",
                values_str(),
                qualifiers_part
            ),
        },
        "ms2neutrallosscondition" => match lang {
            Lang::English => format!(
                "Finding MS2 neutral loss peak at m/z {}{}.",
                values_str(),
                qualifiers_part
            ),
        },
        "ms1mzcondition" => match lang {
            Lang::English => format!(
                "Finding MS1 peak at m/z {}{}.",
                values_str(),
                qualifiers_part
            ),
        },
        "ms2precursorcondition" => match lang {
            Lang::English => format!(
                "Finding MS2 spectra with a precursor m/z {}{}.",
                values_str(),
                qualifiers_part
            ),
        },
        "polaritycondition" => match lang {
            Lang::English => {
                let pol = cond
                    .get("value")
                    .and_then(|v| v.as_array())
                    .and_then(|a| a.first())
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let human = match pol {
                    "positivepolarity" => "positive",
                    "negativepolarity" => "negative",
                    _ => pol,
                };
                format!("Restricting to {} polarity scans.", human)
            }
        },
        "rtmincondition" => match lang {
            Lang::English => format!(
                "Keeping scans with retention time greater than {} minutes.",
                single_value(cond)
            ),
        },
        "rtmaxcondition" => match lang {
            Lang::English => format!(
                "Keeping scans with retention time less than {} minutes.",
                single_value(cond)
            ),
        },
        "scanmincondition" => match lang {
            Lang::English => format!(
                "Keeping scans with scan number at least {}.",
                single_value(cond)
            ),
        },
        "scanmaxcondition" => match lang {
            Lang::English => format!(
                "Keeping scans with scan number at most {}.",
                single_value(cond)
            ),
        },
        "chargecondition" => match lang {
            Lang::English => format!("Requiring precursor charge {}.", single_value(cond)),
        },
        "mobilitycondition" => match lang {
            Lang::English => {
                let (min, max) = range_bounds(cond);
                format!("Keeping scans with ion mobility between {} and {}.", min, max)
            }
        },
        "xcondition" => match lang {
            Lang::English => {
                if cond.get("min").is_some() && cond.get("max").is_some() {
                    let (min, max) = range_bounds(cond);
                    format!("Restricting the variable X to values between {} and {}.", min, max)
                } else if cond.get("mindefect").is_some() && cond.get("maxdefect").is_some() {
                    let min = cond
                        .get("mindefect")
                        .map(|v| v.to_string())
                        .unwrap_or_default();
                    let max = cond
                        .get("maxdefect")
                        .map(|v| v.to_string())
                        .unwrap_or_default();
                    format!(
                        "Restricting the variable X so its mass defect is between {} and {}.",
                        min, max
                    )
                } else {
                    "Introducing an X-variable condition.".into()
                }
            }
        },
        other => match lang {
            Lang::English => format!("Unhandled condition `{}`.", other),
        },
    }
}

fn joined_values(cond: &Value) -> String {
    let values = cond.get("value").and_then(|v| v.as_array());
    match values {
        Some(arr) if !arr.is_empty() => arr
            .iter()
            .map(value_repr)
            .collect::<Vec<_>>()
            .join(" or "),
        _ => "<no value>".into(),
    }
}

fn single_value(cond: &Value) -> String {
    cond.get("value")
        .and_then(|v| v.as_array())
        .and_then(|a| a.first())
        .map(value_repr)
        .unwrap_or_else(|| "<missing>".into())
}

fn value_repr(v: &Value) -> String {
    match v {
        Value::String(s) => s.clone(),
        Value::Number(n) => n.to_string(),
        other => other.to_string(),
    }
}

fn range_bounds(cond: &Value) -> (String, String) {
    let min = cond
        .get("min")
        .map(value_repr)
        .unwrap_or_else(|| "?".into());
    let max = cond
        .get("max")
        .map(value_repr)
        .unwrap_or_else(|| "?".into());
    (min, max)
}

// ==================== qualifiers ====================

fn translate_qualifiers(qualifiers: &Value, lang: Lang) -> String {
    let Some(map) = qualifiers.as_object() else {
        return String::new();
    };
    // Stable alphabetical order so output is deterministic across runs.
    let mut keys: Vec<&String> = map.keys().filter(|k| *k != "type").collect();
    keys.sort();

    let parts: Vec<String> = keys
        .iter()
        .filter_map(|k| map.get(*k).map(|q| translate_qualifier(k, q, lang)))
        .collect();
    match lang {
        Lang::English => parts.join(", "),
    }
}

fn translate_qualifier(key: &str, q: &Value, lang: Lang) -> String {
    let value_str = q
        .get("value")
        .map(value_repr)
        .unwrap_or_else(|| "?".into());
    match (lang, key) {
        (Lang::English, "qualifiermztolerance") => {
            format!("a {} Da m/z tolerance", value_str)
        }
        (Lang::English, "qualifierppmtolerance") => {
            format!("a {} PPM tolerance", value_str)
        }
        (Lang::English, "qualifierintensitypercent") => {
            let cmp = comparator(q);
            format!("intensity {} {}% of base peak", cmp, value_str)
        }
        (Lang::English, "qualifierintensityticpercent") => {
            let cmp = comparator(q);
            format!("intensity {} {}% of TIC", cmp, value_str)
        }
        (Lang::English, "qualifierintensityvalue") => {
            let cmp = comparator(q);
            format!("absolute intensity {} {}", cmp, value_str)
        }
        (Lang::English, "qualifierintensitymatch") => {
            format!("intensity matching {}", value_str)
        }
        (Lang::English, "qualifierintensitytolpercent") => {
            format!("intensity-match tolerance ±{}%", value_str)
        }
        (Lang::English, "qualifierintensityreference") => {
            "marking it as the intensity reference".to_string()
        }
        (Lang::English, "qualifierexcluded") => "excluded".to_string(),
        (Lang::English, "qualifiermassdefect") => {
            let (min, max) = range_bounds(q);
            format!("mass defect in ({}, {})", min, max)
        }
        (Lang::English, "qualifiercardinality") => {
            let (min, max) = range_bounds(q);
            format!("cardinality in ({}, {})", min, max)
        }
        (Lang::English, "qualifierotherscan") => {
            let (min, max) = range_bounds(q);
            format!("other-scan rt window ({}, {})", min, max)
        }
        (Lang::English, other) => format!("qualifier `{}`", other),
    }
}

fn comparator(q: &Value) -> &'static str {
    match q.get("comparator").and_then(|v| v.as_str()) {
        Some("greaterthan") => ">",
        Some("lessthan") => "<",
        _ => "=",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scaninfo_with_tolerance() {
        let got =
            translate_query("QUERY scaninfo(MS2DATA) WHERE MS2PROD=226.18:TOLERANCEPPM=5", Lang::English)
                .unwrap();
        assert!(got.contains("Returning the scan information on MS2"));
        assert!(got.contains("Finding MS2 peak at m/z 226.18"));
        assert!(got.contains("5.0 PPM tolerance"));
    }

    #[test]
    fn polarity_explained() {
        let got = translate_query(
            "QUERY scaninfo(MS1DATA) WHERE POLARITY=Positive",
            Lang::English,
        )
        .unwrap();
        assert!(got.contains("positive polarity scans"));
    }

    #[test]
    fn intensitymatch_reference() {
        let got = translate_query(
            "QUERY scaninfo(MS1DATA) WHERE MS1MZ=X:INTENSITYMATCH=Y:INTENSITYMATCHREFERENCE",
            Lang::English,
        )
        .unwrap();
        assert!(got.contains("intensity matching Y"));
        assert!(got.contains("intensity reference"));
    }

    #[test]
    fn unsupported_language() {
        assert!(matches!(
            Lang::from_str("russian"),
            Err(TranslateError::UnsupportedLang(_))
        ));
    }
}
