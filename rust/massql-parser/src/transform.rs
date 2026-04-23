//! Walks the pest parse tree and emits a `serde_json::Value` whose
//! shape matches `MassQLToJSON().transform(...)` in
//! `massql/msql_parser.py`.
//!
//! The goal is byte-identical output from `serde_json::to_string_pretty`
//! vs Python's `json.dumps(..., sort_keys=True, indent=4)` on the same
//! query. Every deviation we cared about is called out inline.

use pest::iterators::Pair;
use pest::Parser;
use serde_json::{json, Map, Value};
use thiserror::Error;

use crate::grammar::{MsqlParser, Rule};
use crate::masses::{aminoacid_delta_mass, formula_mass, peptide_mass};
use crate::py_float::py_repr_f64;

#[derive(Debug, Error)]
pub enum ParseError {
    #[error("parse error: {0}")]
    Pest(Box<pest::error::Error<Rule>>),
    #[error("semantic error: {0}")]
    Semantic(String),
}

impl From<pest::error::Error<Rule>> for ParseError {
    fn from(e: pest::error::Error<Rule>) -> Self {
        ParseError::Pest(Box::new(e))
    }
}

/// Parse a MassQL query string. Returns the same JSON shape as the
/// Python `parse_msql` — use `serde_json::to_string_pretty` on the
/// result to reproduce the reference fixtures byte-for-byte.
pub fn parse_msql(input: &str) -> Result<Value, ParseError> {
    let cleaned = strip_comments(input);

    let mut pairs = MsqlParser::parse(Rule::statement, &cleaned)?;
    let statement = pairs.next().expect("statement rule matched");
    let mut out = transform_statement(statement)?;
    out.as_object_mut()
        .unwrap()
        .insert("query".into(), Value::String(cleaned));
    Ok(out)
}

/// Mirror of the comment/blank-line stripping in Python `parse_msql`:
/// split on `\n`, `lstrip` each line, drop empties, chop everything at
/// the first `#`, `lstrip` again, drop new empties, rejoin with `\n`.
///
/// NOTE: trailing whitespace is preserved — several reference fixtures
/// include a trailing space in `"query"`.
fn strip_comments(input: &str) -> String {
    input
        .split('\n')
        .map(|s| s.trim_start().to_string())
        .filter(|s| !s.is_empty())
        .map(|s| {
            s.split('#')
                .next()
                .unwrap()
                .trim_start()
                .to_string()
        })
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join("\n")
}

// ==================== statement / querytype ====================

fn transform_statement(pair: Pair<Rule>) -> Result<Value, ParseError> {
    let mut inner = pair.into_inner().peekable();

    // Skip the query keyword.
    let qk = inner.next().unwrap();
    debug_assert_eq!(qk.as_rule(), Rule::querykeyword);

    let querytype = transform_querytype(inner.next().unwrap())?;

    let mut conditions: Vec<Value> = Vec::new();

    while let Some(peek) = inner.peek() {
        match peek.as_rule() {
            Rule::wherekeyword => {
                inner.next();
                while let Some(p) = inner.peek() {
                    if p.as_rule() == Rule::wherefullcondition {
                        let pair = inner.next().unwrap();
                        let subconds =
                            transform_fullcondition(pair, Rule::wherefullcondition, "where")?;
                        conditions.extend(subconds);
                    } else {
                        break;
                    }
                }
            }
            Rule::filterkeyword => {
                inner.next();
                while let Some(p) = inner.peek() {
                    if p.as_rule() == Rule::filterfullcondition {
                        let pair = inner.next().unwrap();
                        let subconds =
                            transform_fullcondition(pair, Rule::filterfullcondition, "filter")?;
                        conditions.extend(subconds);
                    } else {
                        break;
                    }
                }
            }
            Rule::EOI => {
                inner.next();
            }
            _ => {
                inner.next();
            }
        }
    }

    let mut out = Map::new();
    out.insert("querytype".into(), querytype);
    out.insert("conditions".into(), Value::Array(conditions));
    Ok(Value::Object(out))
}

fn transform_querytype(pair: Pair<Rule>) -> Result<Value, ParseError> {
    let inner: Vec<Pair<Rule>> = pair.into_inner().collect();
    let mut map = Map::new();

    if inner.len() == 1 {
        // Just a bare datams1/ms2 data token.
        map.insert("function".into(), Value::Null);
        map.insert("datatype".into(), Value::String(rule_data_name(inner[0].as_rule())));
    } else {
        // function ~ data[ ~ "," ~ param ~ "=" ~ floating ]
        let func_pair = &inner[0];
        debug_assert_eq!(func_pair.as_rule(), Rule::function);
        let func_inner = func_pair.clone().into_inner().next().unwrap();
        map.insert(
            "function".into(),
            Value::String(rule_data_name(func_inner.as_rule())),
        );
        map.insert(
            "datatype".into(),
            Value::String(rule_data_name(inner[1].as_rule())),
        );
        // Lark's transformer ignores the optional TOLERANCE param when
        // building the dict — we do the same. It's parsed but not stored.
    }

    Ok(Value::Object(map))
}

fn rule_data_name(rule: Rule) -> String {
    match rule {
        Rule::datams1data => "datams1data".into(),
        Rule::datams2data => "datams2data".into(),
        Rule::functionscannum => "functionscannum".into(),
        Rule::functionscansum => "functionscansum".into(),
        Rule::functionscanrangesum => "functionscanrangesum".into(),
        Rule::functionscanmz => "functionscanmz".into(),
        Rule::functionscaninfo => "functionscaninfo".into(),
        Rule::functionscanmaxint => "functionscanmaxint".into(),
        other => format!("{:?}", other),
    }
}

// ==================== wherefullcondition / filterfullcondition ====================

fn transform_fullcondition(
    pair: Pair<Rule>,
    single_rule_outer: Rule,
    ctype: &str,
) -> Result<Vec<Value>, ParseError> {
    // Grammar: wherefullcondition = where_single ("AND" where_single)*
    let inner_rule_single = match single_rule_outer {
        Rule::wherefullcondition => Rule::where_single,
        Rule::filterfullcondition => Rule::filter_single,
        _ => unreachable!(),
    };
    let mut out = Vec::new();
    for p in pair.into_inner() {
        match p.as_rule() {
            r if r == inner_rule_single => {
                let cond = transform_single(p, ctype)?;
                out.push(cond);
            }
            Rule::booleanandconjunction => {} // flattened
            _ => {}
        }
    }
    Ok(out)
}

fn transform_single(pair: Pair<Rule>, ctype: &str) -> Result<Value, ParseError> {
    // where_single / filter_single: condition (":" qualifier)?
    let mut inner = pair.into_inner();
    let cond_pair = inner.next().unwrap();
    let mut condition = transform_condition(cond_pair)?;

    if let Some(qual_pair) = inner.next() {
        let qualifier = transform_qualifier(qual_pair)?;
        condition
            .as_object_mut()
            .unwrap()
            .insert("qualifiers".into(), qualifier);
    }
    condition
        .as_object_mut()
        .unwrap()
        .insert("conditiontype".into(), Value::String(ctype.into()));
    Ok(condition)
}

// ==================== condition ====================

fn transform_condition(pair: Pair<Rule>) -> Result<Value, ParseError> {
    let mut inner = pair.into_inner();
    let first = inner.next().unwrap();
    match first.as_rule() {
        Rule::xcondition => {
            // X = (xrange|xdefect)(min=..., max=...)
            let _equal = inner.next().unwrap();
            let xfn = inner.next().unwrap(); // xfunction wrapping xrange|xdefect
            let xfn_inner = xfn.into_inner().next().unwrap();
            let min_expr = transform_numexpr(inner.next().unwrap())?;
            let max_expr = transform_numexpr(inner.next().unwrap())?;

            let mut map = Map::new();
            map.insert("type".into(), Value::String("xcondition".into()));
            match xfn_inner.as_rule() {
                Rule::xdefect => {
                    map.insert("mindefect".into(), coerce_to_float(&min_expr)?);
                    map.insert("maxdefect".into(), coerce_to_float(&max_expr)?);
                }
                Rule::xrange => {
                    map.insert("min".into(), coerce_to_float(&min_expr)?);
                    map.insert("max".into(), coerce_to_float(&max_expr)?);
                }
                _ => unreachable!(),
            }
            Ok(Value::Object(map))
        }
        Rule::mobilitycondition => {
            let _equal = inner.next().unwrap();
            let _mobfn = inner.next().unwrap();
            let min_expr = transform_numexpr(inner.next().unwrap())?;
            let max_expr = transform_numexpr(inner.next().unwrap())?;
            let mut map = Map::new();
            map.insert("type".into(), Value::String("mobilitycondition".into()));
            // Unlike xcondition, mobility preserves the raw numerical
            // expression (string if it contains a variable, number otherwise).
            map.insert("min".into(), min_expr);
            map.insert("max".into(), max_expr);
            Ok(Value::Object(map))
        }
        Rule::polaritycondition => {
            let _equal = inner.next().unwrap();
            let pol = inner.next().unwrap();
            let pol_name = match pol.as_rule() {
                Rule::positivepolarity => "positivepolarity",
                Rule::negativepolarity => "negativepolarity",
                _ => unreachable!(),
            };
            let mut map = Map::new();
            map.insert("type".into(), Value::String("polaritycondition".into()));
            map.insert(
                "value".into(),
                Value::Array(vec![Value::String(pol_name.into())]),
            );
            Ok(Value::Object(map))
        }
        Rule::conditionfields => {
            let field_name = condition_field_name(&first);
            let _equal = inner.next().unwrap();
            let rhs = inner.next().unwrap();

            let value = match rhs.as_rule() {
                Rule::wildcard => Value::Array(vec![Value::String("ANY".into())]),
                Rule::numericalexpressionwithor => transform_numexpr_or(rhs)?,
                Rule::numericalexpression => {
                    let v = transform_numexpr(rhs)?;
                    Value::Array(vec![v])
                }
                Rule::statement => {
                    // Nested statement — not used by current fixtures.
                    return Err(ParseError::Semantic(
                        "nested statement inside condition is not yet supported".into(),
                    ));
                }
                other => {
                    return Err(ParseError::Semantic(format!(
                        "unexpected rhs in condition: {:?}",
                        other
                    )))
                }
            };

            let mut map = Map::new();
            map.insert("type".into(), Value::String(field_name));
            map.insert("value".into(), value);
            Ok(Value::Object(map))
        }
        other => Err(ParseError::Semantic(format!(
            "unexpected condition head: {:?}",
            other
        ))),
    }
}

fn condition_field_name(pair: &Pair<Rule>) -> String {
    let inner = pair.clone().into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::ms2productcondition => "ms2productcondition".into(),
        Rule::ms2precursorcondition => "ms2precursorcondition".into(),
        Rule::ms2neutrallosscondition => "ms2neutrallosscondition".into(),
        Rule::ms1mzcondition => "ms1mzcondition".into(),
        Rule::rtmincondition => "rtmincondition".into(),
        Rule::rtmaxcondition => "rtmaxcondition".into(),
        Rule::scanmincondition => "scanmincondition".into(),
        Rule::scanmaxcondition => "scanmaxcondition".into(),
        Rule::chargecondition => "chargecondition".into(),
        other => format!("{:?}", other),
    }
}

fn coerce_to_float(v: &Value) -> Result<Value, ParseError> {
    // xcondition always wraps via float() in Python; a string here would
    // have meant a variable leaked through, which is a semantic error.
    match v {
        Value::Number(n) => Ok(Value::Number(n.clone())),
        _ => Err(ParseError::Semantic(format!(
            "xcondition range needs a numeric value, got {:?}",
            v
        ))),
    }
}

// ==================== qualifier ====================

fn transform_qualifier(pair: Pair<Rule>) -> Result<Value, ParseError> {
    // qualifier: qualifier_atom (":" qualifier_atom)*
    // Merge all atom dicts into one.
    let mut merged = Map::new();
    merged.insert("type".into(), Value::String("qualifier".into()));
    for atom in pair.into_inner() {
        if atom.as_rule() != Rule::qualifier_atom {
            continue;
        }
        let atom_map = transform_qualifier_atom(atom)?;
        for (k, v) in atom_map {
            if k == "type" {
                continue; // keep the outer type field
            }
            merged.insert(k, v);
        }
    }
    Ok(Value::Object(merged))
}

fn transform_qualifier_atom(pair: Pair<Rule>) -> Result<Map<String, Value>, ParseError> {
    let mut inner = pair.into_inner().peekable();
    let head = inner.next().unwrap();

    let mut map = Map::new();

    match head.as_rule() {
        Rule::qualifierintensityreference => {
            let mut body = Map::new();
            body.insert(
                "name".into(),
                Value::String("qualifierintensityreference".into()),
            );
            map.insert("qualifierintensityreference".into(), Value::Object(body));
        }
        Rule::qualifierexclude => {
            let mut body = Map::new();
            body.insert("name".into(), Value::String("qualifierexcluded".into()));
            map.insert("qualifierexcluded".into(), Value::Object(body));
        }
        Rule::qualifiermassdefect => {
            // qualifiermassdefect equal xdefect (min=..., max=...)
            let _equal = inner.next().unwrap();
            let _xdefect = inner.next().unwrap();
            let min_v = transform_numexpr(inner.next().unwrap())?;
            let max_v = transform_numexpr(inner.next().unwrap())?;
            let mut body = Map::new();
            body.insert("name".into(), Value::String("qualifiermassdefect".into()));
            body.insert("min".into(), min_v);
            body.insert("max".into(), max_v);
            map.insert("qualifiermassdefect".into(), Value::Object(body));
        }
        Rule::qualifiercardinality => {
            let _equal = inner.next().unwrap();
            let _xrange = inner.next().unwrap();
            let min_v = transform_numexpr(inner.next().unwrap())?;
            let max_v = transform_numexpr(inner.next().unwrap())?;
            let mut body = Map::new();
            body.insert("name".into(), Value::String("qualifiercardinality".into()));
            body.insert("min".into(), min_v);
            body.insert("max".into(), max_v);
            map.insert("qualifiercardinality".into(), Value::Object(body));
        }
        Rule::qualifierotherscan => {
            let _equal = inner.next().unwrap();
            let _rtrange = inner.next().unwrap();
            let min_v = transform_numexpr(inner.next().unwrap())?;
            let max_v = transform_numexpr(inner.next().unwrap())?;
            let mut body = Map::new();
            body.insert("name".into(), Value::String("qualifierotherscan".into()));
            body.insert("min".into(), min_v);
            body.insert("max".into(), max_v);
            map.insert("qualifierotherscan".into(), Value::Object(body));
        }
        Rule::qualifierfields => {
            let qname = qualifier_field_name(&head);
            let op = inner.next().unwrap();
            let comparator = match op.as_rule() {
                Rule::equal => "equal",
                Rule::greaterthan => "greaterthan",
                Rule::lessthan => "lessthan",
                _ => unreachable!(),
            };
            let value = transform_numexpr(inner.next().unwrap())?;

            let mut body = Map::new();
            body.insert("name".into(), Value::String(qname.clone()));
            body.insert("comparator".into(), Value::String(comparator.into()));
            if qname == "qualifierppmtolerance" {
                body.insert("unit".into(), Value::String("ppm".into()));
            } else if qname == "qualifiermztolerance" {
                body.insert("unit".into(), Value::String("mz".into()));
            }

            // INTENSITYMATCH keeps the raw numerical-expression value
            // (possibly a string with X/Y); everything else forces float.
            if qname == "qualifierintensitymatch" {
                body.insert("value".into(), value);
            } else {
                body.insert("value".into(), coerce_to_float(&value)?);
            }

            map.insert(qname, Value::Object(body));
        }
        other => {
            return Err(ParseError::Semantic(format!(
                "unexpected qualifier_atom head: {:?}",
                other
            )))
        }
    }

    Ok(map)
}

fn qualifier_field_name(pair: &Pair<Rule>) -> String {
    let inner = pair.clone().into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::qualifiermztolerance => "qualifiermztolerance".into(),
        Rule::qualifierppmtolerance => "qualifierppmtolerance".into(),
        Rule::qualifierintensitypercent => "qualifierintensitypercent".into(),
        Rule::qualifierintensityticpercent => "qualifierintensityticpercent".into(),
        Rule::qualifierintensityvalue => "qualifierintensityvalue".into(),
        Rule::qualifierintensitymatch => "qualifierintensitymatch".into(),
        Rule::qualifierintensitytolpercent => "qualifierintensitytolpercent".into(),
        other => format!("{:?}", other),
    }
}

// ==================== numerical expressions ====================

/// Represents a numerical expression while we build it up: either a
/// concrete float value (no X/Y anywhere in the subtree) or a string
/// that reproduces the expression with Python `str(float)` formatting.
#[derive(Debug, Clone)]
enum NumExpr {
    Value(f64),
    Str(String),
}

impl NumExpr {
    fn to_json(&self) -> Value {
        match self {
            NumExpr::Value(v) => json!(*v),
            NumExpr::Str(s) => Value::String(s.clone()),
        }
    }

    fn stringify(&self) -> String {
        match self {
            NumExpr::Value(v) => py_repr_f64(*v),
            NumExpr::Str(s) => s.clone(),
        }
    }

    fn has_variable(&self) -> bool {
        match self {
            NumExpr::Value(_) => false,
            NumExpr::Str(s) => s.contains('X') || s.contains('Y'),
        }
    }
}

fn transform_numexpr(pair: Pair<Rule>) -> Result<Value, ParseError> {
    let expr = eval_numexpr(pair)?;
    Ok(expr.to_json())
}

fn transform_numexpr_or(pair: Pair<Rule>) -> Result<Value, ParseError> {
    // numericalexpressionwithor = numericalexpression (OR numericalexpression)*
    let mut list = Vec::new();
    for p in pair.into_inner() {
        if p.as_rule() == Rule::numericalexpression {
            let v = eval_numexpr(p)?;
            list.push(v.to_json());
        }
    }
    Ok(Value::Array(list))
}

fn eval_numexpr(pair: Pair<Rule>) -> Result<NumExpr, ParseError> {
    debug_assert_eq!(pair.as_rule(), Rule::numericalexpression);
    let parts: Vec<Pair<Rule>> = pair.into_inner().collect();

    let first_term = eval_term(parts[0].clone())?;
    if parts.len() == 1 {
        return Ok(first_term);
    }

    // Chain of (op, term) pairs. Match Python's behavior: if ANY piece
    // contains a variable, emit as a concatenated string (no eval);
    // otherwise evaluate left-to-right into a single f64.
    let mut ops_terms: Vec<(Rule, NumExpr)> = Vec::new();
    let mut i = 1;
    while i + 1 < parts.len() + 1 && i < parts.len() {
        let op = parts[i].as_rule();
        let term = eval_term(parts[i + 1].clone())?;
        ops_terms.push((op, term));
        i += 2;
    }

    let any_var = first_term.has_variable() || ops_terms.iter().any(|(_, t)| t.has_variable());

    if any_var {
        let mut out = first_term.stringify();
        for (op, term) in &ops_terms {
            out.push_str(op_char(*op));
            out.push_str(&term.stringify());
        }
        Ok(NumExpr::Str(out))
    } else {
        let mut acc = to_f64(&first_term);
        for (op, term) in ops_terms {
            let v = to_f64(&term);
            acc = match op {
                Rule::plus => acc + v,
                Rule::minus => acc - v,
                _ => unreachable!(),
            };
        }
        Ok(NumExpr::Value(acc))
    }
}

fn eval_term(pair: Pair<Rule>) -> Result<NumExpr, ParseError> {
    debug_assert_eq!(pair.as_rule(), Rule::term);
    let parts: Vec<Pair<Rule>> = pair.into_inner().collect();

    let first_factor = eval_factor(parts[0].clone())?;
    if parts.len() == 1 {
        return Ok(first_factor);
    }

    let mut ops_factors: Vec<(Rule, NumExpr)> = Vec::new();
    let mut i = 1;
    while i < parts.len() {
        let op = parts[i].as_rule();
        let fac = eval_factor(parts[i + 1].clone())?;
        ops_factors.push((op, fac));
        i += 2;
    }

    let any_var = first_factor.has_variable() || ops_factors.iter().any(|(_, f)| f.has_variable());

    if any_var {
        let mut out = first_factor.stringify();
        for (op, fac) in &ops_factors {
            out.push_str(op_char(*op));
            out.push_str(&fac.stringify());
        }
        Ok(NumExpr::Str(out))
    } else {
        let mut acc = to_f64(&first_factor);
        for (op, fac) in ops_factors {
            let v = to_f64(&fac);
            acc = match op {
                Rule::multiply => acc * v,
                Rule::divide => acc / v,
                _ => unreachable!(),
            };
        }
        Ok(NumExpr::Value(acc))
    }
}

fn eval_factor(pair: Pair<Rule>) -> Result<NumExpr, ParseError> {
    debug_assert_eq!(pair.as_rule(), Rule::factor);
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::floating => {
            let v: f64 = inner.as_str().parse().map_err(|e| {
                ParseError::Semantic(format!("bad float literal {:?}: {}", inner.as_str(), e))
            })?;
            Ok(NumExpr::Value(v))
        }
        Rule::variable => Ok(NumExpr::Str(inner.as_str().to_string())),
        Rule::factor_parens => {
            let inner_expr = inner.into_inner().next().unwrap();
            let sub = eval_numexpr(inner_expr)?;
            // factor_parens always wraps the string form in parens to
            // preserve grouping when we emit.
            match sub {
                NumExpr::Value(v) => Ok(NumExpr::Value(v)),
                NumExpr::Str(s) => Ok(NumExpr::Str(format!("({})", s))),
            }
        }
        Rule::formula_expr => {
            let formula = inner.into_inner().next().unwrap().as_str();
            let mass = formula_mass(formula).map_err(ParseError::Semantic)?;
            Ok(NumExpr::Value(mass))
        }
        Rule::aminoaciddelta_expr => {
            let aa = inner.into_inner().next().unwrap().as_str();
            let mass = aminoacid_delta_mass(aa).map_err(ParseError::Semantic)?;
            Ok(NumExpr::Value(mass))
        }
        Rule::peptide_expr => {
            let mut it = inner.into_inner();
            let pep = it.next().unwrap().as_str();
            let charge: u32 = it.next().unwrap().as_str().parse().unwrap();
            let ion = it.next().unwrap().as_str().chars().next().unwrap();
            let mass = peptide_mass(pep, ion, charge).map_err(ParseError::Semantic)?;
            Ok(NumExpr::Value(mass))
        }
        other => Err(ParseError::Semantic(format!(
            "unexpected factor inner: {:?}",
            other
        ))),
    }
}

fn to_f64(e: &NumExpr) -> f64 {
    match e {
        NumExpr::Value(v) => *v,
        NumExpr::Str(_) => {
            // Unreachable if `has_variable` is consulted first; we only
            // evaluate numerically when no variable is present.
            panic!("to_f64 called on a string NumExpr — should have gone down the string path");
        }
    }
}

fn op_char(rule: Rule) -> &'static str {
    match rule {
        Rule::plus => "+",
        Rule::minus => "-",
        Rule::multiply => "*",
        Rule::divide => "/",
        _ => panic!("not an operator rule: {:?}", rule),
    }
}

