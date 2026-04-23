//! MassQL parser — Rust port of `massql/msql_parser.py`.
//!
//! The public entry point is [`parse_msql`], which returns a
//! [`serde_json::Value`] whose layout matches the Python reference
//! implementation (same keys, same nesting, same types).
//!
//! The JSON is intentionally kept as `serde_json::Value` so that callers
//! can either read fields directly or serialize via
//! `serde_json::to_string_pretty` to produce byte-identical output to
//! Python's `json.dumps(..., sort_keys=True, indent=4)`. The default
//! `serde_json::Map` is backed by `BTreeMap`, so `to_string_pretty`
//! already emits keys in sorted order.

mod grammar;
mod masses;
pub mod py_float;
mod transform;

pub use grammar::{MsqlParser, Rule};
pub use transform::{parse_msql, ParseError};
