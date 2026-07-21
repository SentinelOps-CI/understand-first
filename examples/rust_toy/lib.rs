//! Multi-file crate fixture for Understand-First Wave 26.
//!
//! Declares child modules and a ``use`` import so call edges can resolve
//! uniquely within the scanned tree (no invent without mod/use evidence).

mod math;
mod helper;

use helper::helper_fn;

/// Bare call gated by ``use helper::helper_fn``.
pub fn run_imported() -> i32 {
    helper_fn()
}

/// Path call gated by ``mod helper``.
pub fn run_mod_path() -> i32 {
    helper::other_fn()
}
