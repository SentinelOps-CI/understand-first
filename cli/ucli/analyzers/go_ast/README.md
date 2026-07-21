# Go AST worker (Wave 19 / Wave 28)

Small `go/parser` + `go/ast` program used by Understand-First when the
`go` toolchain is on PATH. Emits per-file functions plus import specs
(Wave 28). Cross-package call edges are resolved invent-free in Python when
an import path uniquely maps under the scan root (via nearest `go.mod`).

```bash
# From repo root (or any cwd); the Python bridge sets cwd to this directory.
printf '%s' '{"root":"/abs/path","files":["pkg/math.go"]}' | go run .
```

Requires Go 1.21+. When unavailable, the Python adapter falls back to
`go-best-effort` regex heuristics (`UF_GO_ANALYZER=regex|ast|auto`).
Regex path stays same-file-only (no import-path invent).
