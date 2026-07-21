# Rust AST worker (Wave 23–26)

Parse-only [`syn`](https://docs.rs/syn) extractor used when `cargo` is on PATH.

```bash
printf '%s' '{"root":"/abs","files":["math.rs"]}' | cargo run --quiet --manifest-path cli/ucli/analyzers/rust_ast/Cargo.toml
```

Requires Rust 1.70+ / cargo. When unavailable, the Python adapter falls back to
`rust-best-effort` regex (`UF_RUST_ANALYZER=regex|ast|auto`).

Emits per-file `mods` / `uses` so the Python adapter can qualify invent-free
cross-module call edges for unique scanned targets (Wave 26). Glob `use` and
ambiguous names are omitted.

`target/` is build output — safe to delete; first run compiles dependencies.
