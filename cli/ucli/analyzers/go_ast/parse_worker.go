// Understand-First Go AST worker (Wave 19 / Wave 28).
//
// Uses go/parser + go/ast (parse only — no typecheck).
// Wave 28 emits import specs so the Python adapter can invent-free-qualify
// selector calls when an import path uniquely maps inside the scan root.
//
// Complexity formula (ast-cyclomatic), documented for map consumers:
//   1 + count of decision points in the function body, not descending into
//   nested FuncLit bodies:
//     IfStmt, ForStmt, RangeStmt, CaseClause, CommClause,
//     BinaryExpr with LAND (&&) or LOR (||)
//
// Reads a JSON request from stdin:
//   { "root": "<abs>", "files": ["rel/or/abs.go", ...] }
// Writes a JSON response to stdout.
package main

import (
	"encoding/json"
	"fmt"
	"go/ast"
	"go/parser"
	"go/token"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

const complexityFormula = "1 + If/For/Range/CaseClause/CommClause/&&/||; nested FuncLit bodies excluded"

type request struct {
	Root  string   `json:"root"`
	Files []string `json:"files"`
}

type funcMeta struct {
	Line       int      `json:"line"`
	Complexity int      `json:"complexity"`
	Calls      []string `json:"calls"`
	SimpleName string   `json:"simple_name"`
	Type       string   `json:"type"`
	Name       string   `json:"name"`
}

// importSpec is a single import path binding (Wave 28).
// Name is "" for default imports (caller uses the package clause name),
// "." for dot-import, "_" for blank, or an explicit alias.
type importSpec struct {
	Path string `json:"path"`
	Name string `json:"name"`
}

type fileResult struct {
	File      string              `json:"file"`
	Package   string              `json:"package,omitempty"`
	Imports   []importSpec        `json:"imports,omitempty"`
	Functions map[string]funcMeta `json:"functions"`
}

type response struct {
	OK                bool         `json:"ok"`
	Error             string       `json:"error,omitempty"`
	ComplexityFormula string       `json:"complexity_formula,omitempty"`
	Files             []fileResult `json:"files,omitempty"`
}

func writeErr(msg string) {
	_ = json.NewEncoder(os.Stdout).Encode(response{OK: false, Error: msg})
}

func main() {
	raw, err := io.ReadAll(os.Stdin)
	if err != nil {
		writeErr(fmt.Sprintf("read stdin: %v", err))
		os.Exit(1)
	}
	var req request
	if err := json.Unmarshal(raw, &req); err != nil {
		writeErr(fmt.Sprintf("invalid JSON: %v", err))
		os.Exit(1)
	}
	if req.Root == "" {
		writeErr("root is required")
		os.Exit(1)
	}
	root := filepath.Clean(req.Root)
	out := response{
		OK:                true,
		ComplexityFormula: complexityFormula,
		Files:             make([]fileResult, 0, len(req.Files)),
	}
	for _, rel := range req.Files {
		rel = filepath.ToSlash(strings.TrimSpace(rel))
		if rel == "" || !strings.HasSuffix(strings.ToLower(rel), ".go") {
			continue
		}
		abs := rel
		if !filepath.IsAbs(rel) {
			abs = filepath.Join(root, filepath.FromSlash(rel))
		}
		abs = filepath.Clean(abs)
		display, err := filepath.Rel(root, abs)
		if err != nil {
			display = rel
		}
		display = filepath.ToSlash(display)
		fr, err := parseFile(abs, display)
		if err != nil {
			// Soft-skip unreadable/unparseable files (honest empty funcs).
			out.Files = append(out.Files, fileResult{
				File:      display,
				Functions: map[string]funcMeta{},
			})
			continue
		}
		out.Files = append(out.Files, fr)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(out); err != nil {
		os.Exit(1)
	}
}

func parseFile(absPath, display string) (fileResult, error) {
	fset := token.NewFileSet()
	f, err := parser.ParseFile(fset, absPath, nil, parser.ParseComments)
	if err != nil {
		return fileResult{}, err
	}
	funcs := map[string]funcMeta{}
	for _, decl := range f.Decls {
		fd, ok := decl.(*ast.FuncDecl)
		if !ok || fd.Name == nil {
			continue
		}
		local := fd.Name.Name
		simple := local
		ftype := "function"
		if fd.Recv != nil && len(fd.Recv.List) > 0 {
			recvType := recvTypeName(fd.Recv.List[0].Type)
			if recvType != "" {
				local = recvType + "." + fd.Name.Name
				ftype = "method"
			}
		}
		body := fd.Body
		calls := extractCalls(body, fd.Name.Name)
		funcs[local] = funcMeta{
			Line:       fset.Position(fd.Pos()).Line,
			Complexity: decisionComplexity(body),
			Calls:      calls,
			SimpleName: simple,
			Type:       ftype,
			Name:       local,
		}
	}
	pkg := ""
	if f.Name != nil {
		pkg = f.Name.Name
	}
	return fileResult{
		File:      display,
		Package:   pkg,
		Imports:   extractImports(f),
		Functions: funcs,
	}, nil
}

func extractImports(f *ast.File) []importSpec {
	out := []importSpec{}
	if f == nil {
		return out
	}
	for _, imp := range f.Imports {
		if imp == nil || imp.Path == nil {
			continue
		}
		path, err := strconv.Unquote(imp.Path.Value)
		if err != nil || path == "" {
			continue
		}
		name := ""
		if imp.Name != nil {
			name = imp.Name.Name
		}
		out = append(out, importSpec{Path: path, Name: name})
	}
	return out
}

func recvTypeName(expr ast.Expr) string {
	switch t := expr.(type) {
	case *ast.Ident:
		return t.Name
	case *ast.StarExpr:
		return recvTypeName(t.X)
	case *ast.IndexExpr:
		return recvTypeName(t.X)
	case *ast.IndexListExpr:
		return recvTypeName(t.X)
	default:
		return ""
	}
}

func decisionComplexity(body *ast.BlockStmt) int {
	if body == nil {
		return 1
	}
	score := 1
	ast.Inspect(body, func(n ast.Node) bool {
		if n == nil {
			return true
		}
		// Do not descend into nested function literals.
		if _, ok := n.(*ast.FuncLit); ok {
			return false
		}
		switch x := n.(type) {
		case *ast.IfStmt, *ast.ForStmt, *ast.RangeStmt:
			score++
		case *ast.CaseClause, *ast.CommClause:
			score++
		case *ast.BinaryExpr:
			if x.Op == token.LAND || x.Op == token.LOR {
				score++
			}
		}
		return true
	})
	return score
}

func extractCalls(body *ast.BlockStmt, selfName string) []string {
	out := []string{}
	if body == nil {
		return out
	}
	seen := map[string]struct{}{}
	ast.Inspect(body, func(n ast.Node) bool {
		if n == nil {
			return true
		}
		if _, ok := n.(*ast.FuncLit); ok {
			return false
		}
		ce, ok := n.(*ast.CallExpr)
		if !ok {
			return true
		}
		token := callToken(ce.Fun)
		if token == "" || token == selfName {
			return true
		}
		// Skip builtins that are never defs in user code maps.
		switch token {
		case "make", "len", "cap", "append", "copy", "delete", "close",
			"panic", "recover", "print", "println", "new", "complex",
			"real", "imag", "min", "max", "clear":
			return true
		}
		if _, ok := seen[token]; ok {
			return true
		}
		seen[token] = struct{}{}
		out = append(out, token)
		return true
	})
	return out
}

func callToken(expr ast.Expr) string {
	switch e := expr.(type) {
	case *ast.Ident:
		return e.Name
	case *ast.SelectorExpr:
		if id, ok := e.X.(*ast.Ident); ok {
			return id.Name + "." + e.Sel.Name
		}
		return "?." + e.Sel.Name
	default:
		return ""
	}
}
