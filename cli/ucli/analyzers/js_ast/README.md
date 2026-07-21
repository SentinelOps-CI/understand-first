# Optional Node worker for JS/TS AST maps (Wave 17)

Install once (Node 18+):

```bash
cd cli/ucli/analyzers/js_ast
npm install
```

The Python analyzer invokes `parse_worker.mjs` via `node` when
`UF_JS_ANALYZER` is `auto` (default) or `ast`. If Node or the
`typescript` package is missing, Understand-First falls back to the
regex adapter (`javascript-best-effort`).

Force paths:

- `UF_JS_ANALYZER=regex` — always regex
- `UF_JS_ANALYZER=ast` — fail if AST backend unavailable
- `UF_JS_AST_TIMEOUT` — worker timeout seconds (default 60)
