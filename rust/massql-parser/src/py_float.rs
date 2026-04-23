//! Python-compatible float → string formatting.
//!
//! The Python reference parser embeds computed and input floats into the
//! generated JSON as strings whenever a numerical expression contains a
//! variable (X/Y). Those strings come from `str(f)` in Python 3, which is
//! defined by the shortest round-trip representation plus these rules:
//!
//! * Scientific notation kicks in when `abs(x) < 1e-4` or `abs(x) >= 1e16`.
//! * In scientific form:
//!     * The mantissa keeps a `.` **only if** it has fractional digits
//!       (`str(2e-6) == "2e-06"`, `str(2.5e-6) == "2.5e-06"`).
//!     * The exponent always has a `+` or `-` sign and is zero-padded
//!       to at least two digits.
//! * In fixed form the result always contains a `.` (so `2.0`, not `2`).
//!
//! We use `ryu` to get the shortest round-trip decimal digits, then
//! reshape the output to match Python.

pub fn py_repr_f64(x: f64) -> String {
    if x.is_nan() {
        return "nan".to_string();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    if x == 0.0 {
        return if x.is_sign_negative() { "-0.0".into() } else { "0.0".into() };
    }

    let abs = x.abs();
    let use_scientific = abs < 1e-4 || abs >= 1e16;

    // Decompose into a normalized (mantissa, exponent) pair from ryu's
    // shortest round-trip output. ryu may emit either "123.456" or
    // "1.23e-5"; unify the two by computing the decimal exponent of the
    // first significant digit.
    let mut buf = ryu::Buffer::new();
    let ryu_str = buf.format(x);

    let (digits, ryu_exp) = decompose_ryu(ryu_str);

    if use_scientific {
        format_scientific(x.is_sign_negative(), &digits, ryu_exp)
    } else {
        format_fixed(x.is_sign_negative(), &digits, ryu_exp)
    }
}

/// Break ryu's output (e.g. `"12.34"`, `"1.23e-5"`) into a string of
/// significant digits (no leading zeros, no decimal point) and the
/// decimal exponent `e` such that `x = 0.<digits> * 10^(e+1)`.
///
/// Equivalently, the first significant digit represents `10^e`.
fn decompose_ryu(s: &str) -> (String, i32) {
    let s = s.trim_start_matches('-');
    let (mantissa_part, ryu_exp) = match s.find('e') {
        Some(i) => {
            let exp: i32 = s[i + 1..].parse().expect("ryu exponent should parse");
            (&s[..i], exp)
        }
        None => (s, 0),
    };

    // Split mantissa on '.', count digits before/after.
    let (int_part, frac_part) = match mantissa_part.find('.') {
        Some(i) => (&mantissa_part[..i], &mantissa_part[i + 1..]),
        None => (mantissa_part, ""),
    };

    // All digits, in order.
    let mut digits: String = int_part.chars().chain(frac_part.chars()).collect();

    // Position of the decimal point if we interpret `digits` as
    // "int_part . frac_part". That point lands at index `int_part.len()`.
    //
    // The first significant digit sits at index `leading_zeros` in
    // `digits`; removing leading zeros shifts the implicit decimal point.
    let leading_zeros = digits.chars().take_while(|&c| c == '0').count();
    if leading_zeros == digits.len() {
        // Pure zero — caller should have handled this, but be safe.
        return ("0".into(), 0);
    }
    digits.drain(..leading_zeros);

    // Exponent of the first significant digit: it's originally at
    // position `leading_zeros`, the decimal point is at position
    // `int_part.len()`, and ryu applied an extra `ryu_exp`.
    //
    // If there were N integer digits, the leading digit originally
    // represented 10^(N-1). After removing `leading_zeros` from the
    // front, the new leading digit represents 10^(N-1-leading_zeros),
    // then scaled by ryu_exp.
    let exp = (int_part.len() as i32 - 1) - (leading_zeros as i32) + ryu_exp;

    // Strip trailing zeros from the significant digits — shortest round
    // trip shouldn't emit them, but be defensive.
    while digits.len() > 1 && digits.ends_with('0') {
        digits.pop();
    }

    (digits, exp)
}

fn format_scientific(negative: bool, digits: &str, exp: i32) -> String {
    let sign = if negative { "-" } else { "" };
    // Python strips a trailing ".0" but keeps real fractional digits.
    let mantissa = if digits.len() == 1 {
        digits.to_string()
    } else {
        format!("{}.{}", &digits[..1], &digits[1..])
    };
    let exp_sign = if exp < 0 { '-' } else { '+' };
    format!("{}{}e{}{:02}", sign, mantissa, exp_sign, exp.abs())
}

fn format_fixed(negative: bool, digits: &str, exp: i32) -> String {
    let sign = if negative { "-" } else { "" };
    let body = if exp >= 0 {
        let int_digits = exp as usize + 1;
        if digits.len() <= int_digits {
            // Need to pad with zeros on the right, then add ".0".
            let pad = int_digits - digits.len();
            let mut s = String::with_capacity(int_digits + 2);
            s.push_str(digits);
            for _ in 0..pad {
                s.push('0');
            }
            s.push_str(".0");
            s
        } else {
            let (int_part, frac_part) = digits.split_at(int_digits);
            format!("{}.{}", int_part, frac_part)
        }
    } else {
        // exp is negative: result is 0.<leading zeros><digits>
        let leading = (-exp - 1) as usize;
        let mut s = String::with_capacity(2 + leading + digits.len());
        s.push_str("0.");
        for _ in 0..leading {
            s.push('0');
        }
        s.push_str(digits);
        s
    };
    format!("{}{}", sign, body)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_python_str_repr() {
        // These are the values we've observed in the fixtures plus a
        // few representative edge cases — each left side is what
        // Python 3's `str(x)` produces.
        let cases: &[(f64, &str)] = &[
            (2.0, "2.0"),
            (0.1, "0.1"),
            (100.0, "100.0"),
            (226.18, "226.18"),
            (0.000002, "2e-06"),
            (55.9349375, "55.9349375"),
            (120.0, "120.0"),
            (5.0, "5.0"),
            (-2.0, "-2.0"),
            (0.0, "0.0"),
            (1e16, "1e+16"),
            (1e-5, "1e-05"),
            (0.0001, "0.0001"),
        ];
        for (x, expected) in cases {
            let got = py_repr_f64(*x);
            assert_eq!(got, *expected, "py_repr_f64({})", x);
        }
    }
}
