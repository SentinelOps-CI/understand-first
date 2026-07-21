//! Cross-module helper for Wave 26 invent-free mod/use edges.

pub fn helper_fn() -> i32 {
    1
}

pub fn other_fn() -> i32 {
    helper_fn()
}
