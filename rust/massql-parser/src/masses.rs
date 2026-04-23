//! Monoisotopic atomic and amino-acid residue masses.
//!
//! These are the values pyteomics' `mass.calculate_mass` produces by
//! default — i.e., the most abundant isotope mass for each element, and
//! the residue mass (peptide bond removed, so minus H2O) for each amino
//! acid. The Python reference parser invokes pyteomics with no unit
//! override, so results flow into the JSON as these exact `f64` values
//! (then `str()`-formatted by `py_float::py_repr_f64`).
//!
//! To avoid dragging in an elemental database we hard-code the subset of
//! elements we have observed in queries; add more on demand.

use std::collections::HashMap;

/// Compute the monoisotopic mass of a chemical formula (e.g. `"Fe"`,
/// `"C10"`, `"CH2"`).
pub fn formula_mass(formula: &str) -> Result<f64, String> {
    let atoms = parse_formula(formula)?;
    let mut total = 0.0;
    for (element, count) in atoms {
        let m = element_mass(&element)
            .ok_or_else(|| format!("unknown element: {}", element))?;
        total += m * count as f64;
    }
    Ok(total)
}

/// Compute the mass of an amino-acid sequence, minus the mass of H2O
/// (matching pyteomics' `calculate_mass(sequence=...)` minus
/// `calculate_mass(formula="H2O")` — the "amino acid delta").
pub fn aminoacid_delta_mass(sequence: &str) -> Result<f64, String> {
    let mut total = 0.0;
    for aa in sequence.chars() {
        let m = aminoacid_residue_mass(aa)
            .ok_or_else(|| format!("unknown amino acid: {}", aa))?;
        total += m;
    }
    Ok(total)
}

/// Compute the m/z of a peptide fragment ion. Mirrors
/// `pyteomics.mass.calculate_mass(sequence=peptide, ion_type=ion, charge=charge)`.
pub fn peptide_mass(_peptide: &str, _ion: char, _charge: u32) -> Result<f64, String> {
    // Full pyteomics-compatible ion m/z calculation isn't needed for the
    // current fixture set. Left as TODO until a peptide-using fixture is
    // added; returning an error surfaces the gap clearly.
    Err("peptide(...) expression not yet implemented in Rust port".into())
}

fn parse_formula(s: &str) -> Result<Vec<(String, u32)>, String> {
    let mut out = Vec::new();
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if !bytes[i].is_ascii_uppercase() {
            return Err(format!("invalid formula char at {}: {:?}", i, bytes[i] as char));
        }
        let start = i;
        i += 1;
        while i < bytes.len() && bytes[i].is_ascii_lowercase() {
            i += 1;
        }
        let element = std::str::from_utf8(&bytes[start..i]).unwrap().to_string();

        let num_start = i;
        while i < bytes.len() && bytes[i].is_ascii_digit() {
            i += 1;
        }
        let count: u32 = if i == num_start {
            1
        } else {
            std::str::from_utf8(&bytes[num_start..i]).unwrap().parse().unwrap()
        };
        out.push((element, count));
    }
    Ok(out)
}

fn element_mass(el: &str) -> Option<f64> {
    // Monoisotopic masses from pyteomics' default table (NIST values).
    // Only elements that appear in real MassQL queries — extend as needed.
    match el {
        "H" => Some(1.00782503207),
        "C" => Some(12.0),
        "N" => Some(14.0030740048),
        "O" => Some(15.99491461956),
        "S" => Some(31.97207100),
        "P" => Some(30.97376163),
        "F" => Some(18.99840322),
        "Cl" => Some(34.96885268),
        "Br" => Some(78.9183371),
        "I" => Some(126.904473),
        "Na" => Some(22.9897692809),
        "K" => Some(38.96370668),
        "Fe" => Some(55.9349375),
        "Mg" => Some(23.9850417),
        "Ca" => Some(39.96259098),
        "Mn" => Some(54.9380451),
        "Zn" => Some(63.9291422),
        "Cu" => Some(62.9295975),
        "Se" => Some(79.9165213),
        _ => None,
    }
}

fn aminoacid_residue_mass(aa: char) -> Option<f64> {
    // Residue monoisotopic masses (no water). Kept inline so the
    // fixture-parity test doesn't need to reach into pyteomics.
    static TABLE: once_cell::sync::Lazy<HashMap<char, f64>> = once_cell::sync::Lazy::new(|| {
        let mut m = HashMap::new();
        m.insert('A', 71.03711);
        m.insert('R', 156.10111);
        m.insert('N', 114.04293);
        m.insert('D', 115.02694);
        m.insert('C', 103.00919);
        m.insert('E', 129.04259);
        m.insert('Q', 128.05858);
        m.insert('G', 57.02146);
        m.insert('H', 137.05891);
        m.insert('I', 113.08406);
        m.insert('L', 113.08406);
        m.insert('K', 128.09496);
        m.insert('M', 131.04049);
        m.insert('F', 147.06841);
        m.insert('P', 97.05276);
        m.insert('S', 87.03203);
        m.insert('T', 101.04768);
        m.insert('W', 186.07931);
        m.insert('Y', 163.06333);
        m.insert('V', 99.06841);
        m
    });
    TABLE.get(&aa).copied()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formula_fe_matches_reference() {
        // From RESULT_VIEW.md: formula(Fe) = 55.9349375
        assert_eq!(formula_mass("Fe").unwrap(), 55.9349375);
    }

    #[test]
    fn formula_c10_is_exactly_120() {
        assert_eq!(formula_mass("C10").unwrap(), 120.0);
    }
}
