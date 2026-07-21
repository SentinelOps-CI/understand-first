//! Understand-First Rust AST worker (Wave 23).
//!
//! Parse-only via `syn` (not rustc typecheck / MIR).
//! Complexity (ast-cyclomatic): 1 + If/While/For/Loop/MatchArm/Binary &&|| /
//!   Question (?)/IfLet/WhileLet; nested fn/closure bodies excluded.
//!
//! stdin JSON: { "root": "<abs>", "files": ["rel.rs", ...] }
//! stdout JSON: { "ok": true, "files": [...], "complexity_formula": "..." }

use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;
use std::fs;
use std::io::{self, Read};
use std::path::{Path, PathBuf};
use syn::spanned::Spanned;
use syn::visit::Visit;
use syn::{BinOp, Expr, ImplItem, Item, Pat};

const COMPLEXITY_FORMULA: &str = "1 + If/While/For/Loop/MatchArm/IfLet/WhileLet/Question/?=/&&/||; nested fn/closure bodies excluded";

#[derive(Deserialize)]
struct Request {
    root: String,
    files: Vec<String>,
}

#[derive(Serialize)]
struct FuncMeta {
    simple_name: String,
    file: String,
    calls: Vec<String>,
    callers: Vec<String>,
    complexity: usize,
    line: usize,
    language: String,
}

#[derive(Serialize)]
struct FileEntry {
    file: String,
    functions: serde_json::Map<String, serde_json::Value>,
}

#[derive(Serialize)]
struct Response {
    ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    complexity_formula: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    files: Option<Vec<FileEntry>>,
}

fn main() {
    let mut raw = String::new();
    if let Err(e) = io::stdin().read_to_string(&mut raw) {
        emit_err(&format!("read stdin: {e}"));
        std::process::exit(1);
    }
    let req: Request = match serde_json::from_str(&raw) {
        Ok(r) => r,
        Err(e) => {
            emit_err(&format!("invalid JSON: {e}"));
            std::process::exit(1);
        }
    };
    let root = PathBuf::from(&req.root);
    let mut files_out = Vec::new();
    for rel in &req.files {
        let rel = rel.replace('\\', "/");
        if !rel.to_lowercase().ends_with(".rs") {
            continue;
        }
        let abs = if Path::new(&rel).is_absolute() {
            PathBuf::from(&rel)
        } else {
            root.join(Path::new(&rel))
        };
        match parse_file(&abs, &rel) {
            Ok(entry) => files_out.push(entry),
            Err(_) => {
                // Soft-skip unreadable/unparseable files.
                files_out.push(FileEntry {
                    file: rel,
                    functions: serde_json::Map::new(),
                });
            }
        }
    }
    let resp = Response {
        ok: true,
        error: None,
        complexity_formula: Some(COMPLEXITY_FORMULA.to_string()),
        files: Some(files_out),
    };
    if let Err(e) = serde_json::to_writer(io::stdout(), &resp) {
        eprintln!("encode failed: {e}");
        std::process::exit(1);
    }
}

fn emit_err(msg: &str) {
    let _ = serde_json::to_writer(
        io::stdout(),
        &Response {
            ok: false,
            error: Some(msg.to_string()),
            complexity_formula: None,
            files: None,
        },
    );
}

fn parse_file(abs: &Path, display: &str) -> Result<FileEntry, String> {
    let src = fs::read_to_string(abs).map_err(|e| e.to_string())?;
    let file = syn::parse_file(&src).map_err(|e| e.to_string())?;
    let mut funcs = serde_json::Map::new();

    for item in &file.items {
        match item {
            Item::Fn(f) => {
                let name = f.sig.ident.to_string();
                let line = f.sig.ident.span().start().line;
                let meta = extract_fn(display, &name, &name, &f.block, line);
                funcs.insert(name, serde_json::to_value(meta).unwrap());
            }
            Item::Impl(im) => {
                let type_name = type_path_name(&im.self_ty).unwrap_or_else(|| "Unknown".into());
                for it in &im.items {
                    if let ImplItem::Fn(m) = it {
                        let simple = m.sig.ident.to_string();
                        let local = format!("{type_name}.{simple}");
                        let line = m.sig.ident.span().start().line;
                        let meta = extract_fn(display, &local, &simple, &m.block, line);
                        funcs.insert(local, serde_json::to_value(meta).unwrap());
                    }
                }
            }
            _ => {}
        }
    }

    Ok(FileEntry {
        file: display.replace('\\', "/"),
        functions: funcs,
    })
}

fn type_path_name(ty: &syn::Type) -> Option<String> {
    match ty {
        syn::Type::Path(p) => p.path.segments.last().map(|s| s.ident.to_string()),
        syn::Type::Reference(r) => type_path_name(&r.elem),
        syn::Type::Paren(p) => type_path_name(&p.elem),
        _ => None,
    }
}

fn extract_fn(file: &str, _local: &str, simple: &str, block: &syn::Block, line: usize) -> FuncMeta {
    let mut v = BodyVisitor {
        calls: BTreeSet::new(),
        complexity: 1,
    };
    v.visit_block(block);
    FuncMeta {
        simple_name: simple.to_string(),
        file: file.replace('\\', "/"),
        calls: v.calls.into_iter().collect(),
        callers: vec![],
        complexity: v.complexity,
        line: if line == 0 { 1 } else { line },
        language: "rust".into(),
    }
}

struct BodyVisitor {
    calls: BTreeSet<String>,
    complexity: usize,
}

impl<'ast> Visit<'ast> for BodyVisitor {
    fn visit_item_fn(&mut self, _node: &'ast syn::ItemFn) {
        // Nested items: do not descend (counted on their own entries if top-level).
    }

    fn visit_expr_closure(&mut self, _node: &'ast syn::ExprClosure) {
        // Nested closures: exclude body from enclosing CC / calls.
    }

    fn visit_expr_if(&mut self, node: &'ast syn::ExprIf) {
        self.complexity += 1;
        syn::visit::visit_expr_if(self, node);
    }

    fn visit_expr_while(&mut self, node: &'ast syn::ExprWhile) {
        self.complexity += 1;
        syn::visit::visit_expr_while(self, node);
    }

    fn visit_expr_for_loop(&mut self, node: &'ast syn::ExprForLoop) {
        self.complexity += 1;
        syn::visit::visit_expr_for_loop(self, node);
    }

    fn visit_expr_loop(&mut self, node: &'ast syn::ExprLoop) {
        self.complexity += 1;
        syn::visit::visit_expr_loop(self, node);
    }

    fn visit_expr_match(&mut self, node: &'ast syn::ExprMatch) {
        for arm in &node.arms {
            self.complexity += 1;
            self.visit_arm(arm);
        }
        // Don't double-count via default visit of arms
        self.visit_expr(&node.expr);
    }

    fn visit_expr_binary(&mut self, node: &'ast syn::ExprBinary) {
        if matches!(node.op, BinOp::And(_) | BinOp::Or(_)) {
            self.complexity += 1;
        }
        syn::visit::visit_expr_binary(self, node);
    }

    fn visit_expr_try(&mut self, node: &'ast syn::ExprTry) {
        self.complexity += 1;
        syn::visit::visit_expr_try(self, node);
    }

    fn visit_pat(&mut self, node: &'ast Pat) {
        // if let / while let patterns counted via ExprIf/ExprWhile when let present —
        // also bump for IfLetExpr-style via Expr::If with let condition is already If.
        syn::visit::visit_pat(self, node);
    }

    fn visit_expr_call(&mut self, node: &'ast syn::ExprCall) {
        if let Some(name) = call_name(&node.func) {
            if !is_builtin(&name) {
                self.calls.insert(name);
            }
        }
        syn::visit::visit_expr_call(self, node);
    }

    fn visit_expr_method_call(&mut self, node: &'ast syn::ExprMethodCall) {
        let name = node.method.to_string();
        if !is_builtin(&name) {
            self.calls.insert(name);
        }
        syn::visit::visit_expr_method_call(self, node);
    }
}

fn call_name(expr: &Expr) -> Option<String> {
    match expr {
        Expr::Path(p) => p.path.segments.last().map(|s| s.ident.to_string()),
        Expr::Paren(p) => call_name(&p.expr),
        Expr::Group(g) => call_name(&g.expr),
        _ => None,
    }
}

fn is_builtin(name: &str) -> bool {
    matches!(
        name,
        "Some"
            | "None"
            | "Ok"
            | "Err"
            | "vec"
            | "println"
            | "print"
            | "eprintln"
            | "eprint"
            | "format"
            | "panic"
            | "assert"
            | "assert_eq"
            | "assert_ne"
            | "dbg"
            | "todo"
            | "unimplemented"
            | "unreachable"
            | "drop"
            | "Box"
            | "String"
            | "Vec"
    )
}
