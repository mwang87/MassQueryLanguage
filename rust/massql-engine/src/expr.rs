//! Tiny arithmetic-expression evaluator used by the variable pipeline.
//!
//! The parser emits expression strings (like `"X-2.0"`, `"Y*0.66"`,
//! `"Y*(0.0608+(2e-06*X))"`) whenever a numeric expression contains a
//! variable, then formats floats with Python's `str(float)` rules.
//! The engine's variable pipeline substitutes concrete values for `X`
//! and / or `Y` and evaluates the result.
//!
//! Grammar (recursive descent over a whitespace-stripped input):
//!
//! ```text
//!     expr   = term (('+'|'-') term)*
//!     term   = factor (('*'|'/') factor)*
//!     factor = '(' expr ')' | number | identifier
//!     number = floating-point literal
//! ```
//!
//! The full MassQL parser handles more (formula(...) etc.), but by
//! the time we're evaluating a string at engine time those have
//! already been resolved to floats during parse. What's left is
//! just plain arithmetic with zero or more variables.

use std::collections::HashMap;

#[derive(Debug)]
pub enum EvalError {
    Parse(String),
    UndefinedVariable(String),
}

impl std::fmt::Display for EvalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            EvalError::Parse(s) => write!(f, "expression parse error: {}", s),
            EvalError::UndefinedVariable(v) => write!(f, "undefined variable {}", v),
        }
    }
}
impl std::error::Error for EvalError {}

pub type Env = HashMap<String, f64>;

/// Parse and evaluate an arithmetic expression in one step.
pub fn eval(input: &str, env: &Env) -> Result<f64, EvalError> {
    let mut p = Parser::new(input);
    let v = p.parse_expr(env)?;
    p.expect_end()?;
    Ok(v)
}

/// Substitute into a value-string. If the string parses as a pure
/// expression, we evaluate it. If evaluation needs an unbound variable
/// (common when substituting just `X`, leaving `Y` free), we return
/// the original string untouched — matching Python's behavior, which
/// leaves `Y*0.66` as-is until the INTENSITYMATCH reference fires.
pub fn substitute(input: &str, env: &Env) -> String {
    match eval(input, env) {
        Ok(v) => massql_parser::py_float::py_repr_f64(v),
        Err(EvalError::UndefinedVariable(_)) => {
            // Try to partially substitute by re-serializing the AST
            // with the known variables replaced.
            partial_substitute(input, env).unwrap_or_else(|_| input.to_string())
        }
        Err(EvalError::Parse(_)) => input.to_string(),
    }
}

/// Re-emit the expression as a string with the supplied variables
/// bound to their values (numbers) and unknown variables left alone.
/// Used when we can substitute `X` but `Y` is still free.
pub fn partial_substitute(input: &str, env: &Env) -> Result<String, EvalError> {
    let mut p = Parser::new(input);
    let ast = p.parse_ast()?;
    p.expect_end()?;
    Ok(emit(&ast, env))
}

// ==================== AST + recursive descent ====================

#[derive(Debug, Clone)]
enum Ast {
    Num(f64),
    Var(String),
    Bin(char, Box<Ast>, Box<Ast>),
    /// Parenthesized subexpression — tracked separately so we can
    /// round-trip it back to a string with grouping preserved.
    Paren(Box<Ast>),
}

struct Parser<'a> {
    src: &'a str,
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> Parser<'a> {
    fn new(s: &'a str) -> Self {
        Parser { src: s, bytes: s.as_bytes(), pos: 0 }
    }

    fn skip_ws(&mut self) {
        while self.pos < self.bytes.len() && self.bytes[self.pos].is_ascii_whitespace() {
            self.pos += 1;
        }
    }

    fn consume(&mut self, expected: u8) -> bool {
        self.skip_ws();
        if self.bytes.get(self.pos) == Some(&expected) {
            self.pos += 1;
            true
        } else {
            false
        }
    }

    fn expect_end(&mut self) -> Result<(), EvalError> {
        self.skip_ws();
        if self.pos < self.bytes.len() {
            Err(EvalError::Parse(format!(
                "trailing input at {}: {:?}",
                self.pos,
                &self.src[self.pos..]
            )))
        } else {
            Ok(())
        }
    }

    // -------- evaluating parse (early exit to a single f64) --------

    fn parse_expr(&mut self, env: &Env) -> Result<f64, EvalError> {
        let mut acc = self.parse_term(env)?;
        loop {
            self.skip_ws();
            match self.bytes.get(self.pos).copied() {
                Some(b'+') => {
                    self.pos += 1;
                    acc += self.parse_term(env)?;
                }
                Some(b'-') => {
                    self.pos += 1;
                    acc -= self.parse_term(env)?;
                }
                _ => return Ok(acc),
            }
        }
    }

    fn parse_term(&mut self, env: &Env) -> Result<f64, EvalError> {
        let mut acc = self.parse_factor(env)?;
        loop {
            self.skip_ws();
            match self.bytes.get(self.pos).copied() {
                Some(b'*') => {
                    self.pos += 1;
                    acc *= self.parse_factor(env)?;
                }
                Some(b'/') => {
                    self.pos += 1;
                    acc /= self.parse_factor(env)?;
                }
                _ => return Ok(acc),
            }
        }
    }

    fn parse_factor(&mut self, env: &Env) -> Result<f64, EvalError> {
        self.skip_ws();
        match self.bytes.get(self.pos).copied() {
            Some(b'(') => {
                self.pos += 1;
                let v = self.parse_expr(env)?;
                if !self.consume(b')') {
                    return Err(EvalError::Parse("missing `)`".into()));
                }
                Ok(v)
            }
            Some(b'-') => {
                self.pos += 1;
                Ok(-self.parse_factor(env)?)
            }
            Some(b'+') => {
                self.pos += 1;
                self.parse_factor(env)
            }
            Some(c) if c.is_ascii_alphabetic() => {
                let name = self.read_ident();
                env.get(&name)
                    .copied()
                    .ok_or_else(|| EvalError::UndefinedVariable(name))
            }
            Some(c) if c.is_ascii_digit() || c == b'.' => self.read_number(),
            Some(c) => Err(EvalError::Parse(format!("unexpected char {:?}", c as char))),
            None => Err(EvalError::Parse("unexpected end".into())),
        }
    }

    fn read_ident(&mut self) -> String {
        let start = self.pos;
        while self.pos < self.bytes.len()
            && (self.bytes[self.pos].is_ascii_alphanumeric() || self.bytes[self.pos] == b'_')
        {
            self.pos += 1;
        }
        self.src[start..self.pos].to_string()
    }

    fn read_number(&mut self) -> Result<f64, EvalError> {
        let start = self.pos;
        // Mantissa
        while self.pos < self.bytes.len()
            && (self.bytes[self.pos].is_ascii_digit() || self.bytes[self.pos] == b'.')
        {
            self.pos += 1;
        }
        // Exponent
        if self.pos < self.bytes.len() && (self.bytes[self.pos] == b'e' || self.bytes[self.pos] == b'E') {
            self.pos += 1;
            if self.pos < self.bytes.len() && (self.bytes[self.pos] == b'+' || self.bytes[self.pos] == b'-') {
                self.pos += 1;
            }
            while self.pos < self.bytes.len() && self.bytes[self.pos].is_ascii_digit() {
                self.pos += 1;
            }
        }
        self.src[start..self.pos]
            .parse::<f64>()
            .map_err(|e| EvalError::Parse(format!("bad number {:?}: {}", &self.src[start..self.pos], e)))
    }

    // -------- AST parse (used for partial substitution) --------

    fn parse_ast(&mut self) -> Result<Ast, EvalError> {
        let mut lhs = self.parse_term_ast()?;
        loop {
            self.skip_ws();
            let op = match self.bytes.get(self.pos).copied() {
                Some(b'+') => '+',
                Some(b'-') => '-',
                _ => return Ok(lhs),
            };
            self.pos += 1;
            let rhs = self.parse_term_ast()?;
            lhs = Ast::Bin(op, Box::new(lhs), Box::new(rhs));
        }
    }

    fn parse_term_ast(&mut self) -> Result<Ast, EvalError> {
        let mut lhs = self.parse_factor_ast()?;
        loop {
            self.skip_ws();
            let op = match self.bytes.get(self.pos).copied() {
                Some(b'*') => '*',
                Some(b'/') => '/',
                _ => return Ok(lhs),
            };
            self.pos += 1;
            let rhs = self.parse_factor_ast()?;
            lhs = Ast::Bin(op, Box::new(lhs), Box::new(rhs));
        }
    }

    fn parse_factor_ast(&mut self) -> Result<Ast, EvalError> {
        self.skip_ws();
        match self.bytes.get(self.pos).copied() {
            Some(b'(') => {
                self.pos += 1;
                let inner = self.parse_ast()?;
                if !self.consume(b')') {
                    return Err(EvalError::Parse("missing `)`".into()));
                }
                Ok(Ast::Paren(Box::new(inner)))
            }
            Some(b'-') => {
                self.pos += 1;
                // Encode unary minus as `0 - x`. Round-trip-safe for
                // our output format.
                Ok(Ast::Bin('-', Box::new(Ast::Num(0.0)), Box::new(self.parse_factor_ast()?)))
            }
            Some(b'+') => {
                self.pos += 1;
                self.parse_factor_ast()
            }
            Some(c) if c.is_ascii_alphabetic() => {
                let name = self.read_ident();
                Ok(Ast::Var(name))
            }
            Some(c) if c.is_ascii_digit() || c == b'.' => {
                let n = self.read_number()?;
                Ok(Ast::Num(n))
            }
            Some(c) => Err(EvalError::Parse(format!("unexpected char {:?}", c as char))),
            None => Err(EvalError::Parse("unexpected end".into())),
        }
    }
}

fn emit(ast: &Ast, env: &Env) -> String {
    match ast {
        Ast::Num(n) => massql_parser::py_float::py_repr_f64(*n),
        Ast::Var(name) => match env.get(name) {
            Some(v) => massql_parser::py_float::py_repr_f64(*v),
            None => name.clone(),
        },
        Ast::Bin(op, l, r) => format!("{}{}{}", emit(l, env), op, emit(r, env)),
        Ast::Paren(inner) => format!("({})", emit(inner, env)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn env_x(x: f64) -> Env {
        let mut m = Env::new();
        m.insert("X".into(), x);
        m
    }

    #[test]
    fn basic_arithmetic() {
        let e = Env::new();
        assert_eq!(eval("1+2", &e).unwrap(), 3.0);
        assert_eq!(eval("1 + 2 * 3", &e).unwrap(), 7.0);
        assert_eq!(eval("(1 + 2) * 3", &e).unwrap(), 9.0);
        assert_eq!(eval("10 / 2 - 1", &e).unwrap(), 4.0);
    }

    #[test]
    fn variable_substitution() {
        let e = env_x(100.0);
        assert_eq!(eval("X", &e).unwrap(), 100.0);
        assert_eq!(eval("X-2.0", &e).unwrap(), 98.0);
        assert_eq!(eval("X+164.9", &e).unwrap(), 264.9);
        assert_eq!(eval("2.0*(X - 55.9349375)", &e).unwrap(), 88.130125);
    }

    #[test]
    fn partial_substitution_keeps_y() {
        let e = env_x(100.0);
        // Y is undefined but X=100; should render back as "Y*0.66".
        assert_eq!(substitute("Y*0.66", &e), "Y*0.66");
        // With X present, substitute it in.
        assert_eq!(substitute("Y*(0.0608+(2e-06*X))", &e), "Y*(0.0608+(2e-06*100.0))");
    }
}
