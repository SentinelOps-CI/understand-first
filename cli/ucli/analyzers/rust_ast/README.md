# Rust AST worker (Wave 23)

Parse-only [`syn`](https://docs.rs/syn) extractor used when `cargo` is on PATH.

```bash
printf '%s' '{"root":"/abs","files":["math.rs"]}' | cargo run --quiet --manifest-path cli/ucli/analyzers/rust_ast/Cargo.toml
```

Requires Rust 1.70+ / cargo. When unavailable, the Python adapter falls back to
`rust-best-effort` regex (`UF_RUST_ANALYZER=regex|ast|auto`).

`target/` is build output — safe to delete; first run compiles dependencies.
