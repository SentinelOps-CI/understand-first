#!/usr/bin/env node
/**
 * Understand-First JS/TS AST worker (Wave 17).
 *
 * Uses the TypeScript compiler API (parse only — no typecheck program).
 *
 * Complexity formula (``ast-cyclomatic``), documented for map consumers:
 *   1 + count of decision points in the function body, not descending into
 *   nested function/arrow/method bodies:
 *     IfStatement, ForStatement, ForInStatement, ForOfStatement,
 *     WhileStatement, DoWhileStatement, CaseClause, CatchClause,
 *     ConditionalExpression (?:), BinaryExpression with && or ||
 *
 * Reads a JSON request from stdin:
 *   { "root": "<abs>", "files": ["rel/or/abs.js", ...] }
 * Writes a JSON response to stdout.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

function loadTypescript() {
  const candidates = [
    path.join(__dirname, "node_modules", "typescript"),
    "typescript",
  ];
  for (const c of candidates) {
    try {
      return require(c);
    } catch {
      /* try next */
    }
  }
  throw new Error(
    "typescript package not found; run npm install in cli/ucli/analyzers/js_ast",
  );
}

const ts = loadTypescript();

const JS_LIKE = new Set([".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"]);

function scriptKindFor(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case ".ts":
      return ts.ScriptKind.TS;
    case ".tsx":
      return ts.ScriptKind.TSX;
    case ".jsx":
      return ts.ScriptKind.JSX;
    default:
      return ts.ScriptKind.JS;
  }
}

function languageFor(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return ext === ".ts" || ext === ".tsx" ? "typescript" : "javascript";
}

function isFunctionLike(node) {
  return (
    ts.isFunctionDeclaration(node) ||
    ts.isFunctionExpression(node) ||
    ts.isArrowFunction(node) ||
    ts.isMethodDeclaration(node) ||
    ts.isConstructorDeclaration(node) ||
    ts.isGetAccessorDeclaration(node) ||
    ts.isSetAccessorDeclaration(node)
  );
}

function decisionComplexity(body) {
  if (!body) return 1;
  let score = 1;
  const visit = (node) => {
    if (!node) return;
    if (node !== body && isFunctionLike(node)) return;
    switch (node.kind) {
      case ts.SyntaxKind.IfStatement:
      case ts.SyntaxKind.ForStatement:
      case ts.SyntaxKind.ForInStatement:
      case ts.SyntaxKind.ForOfStatement:
      case ts.SyntaxKind.WhileStatement:
      case ts.SyntaxKind.DoWhileStatement:
      case ts.SyntaxKind.CaseClause:
      case ts.SyntaxKind.CatchClause:
      case ts.SyntaxKind.ConditionalExpression:
        score += 1;
        break;
      case ts.SyntaxKind.BinaryExpression:
        if (
          node.operatorToken &&
          (node.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken ||
            node.operatorToken.kind === ts.SyntaxKind.BarBarToken)
        ) {
          score += 1;
        }
        break;
      default:
        break;
    }
    ts.forEachChild(node, visit);
  };
  visit(body);
  return score;
}

function extractCalls(body, selfName) {
  const calls = [];
  const seen = new Set();
  const visit = (node) => {
    if (!node) return;
    if (node !== body && isFunctionLike(node)) return;
    if (ts.isCallExpression(node)) {
      const expr = node.expression;
      let token = null;
      if (ts.isIdentifier(expr)) {
        token = expr.text;
      } else if (
        ts.isPropertyAccessExpression(expr) &&
        ts.isIdentifier(expr.name)
      ) {
        const obj = ts.isIdentifier(expr.expression)
          ? expr.expression.text
          : "?";
        token = `${obj}.${expr.name.text}`;
      }
      if (
        token &&
        token !== selfName &&
        token !== "super" &&
        token !== "require"
      ) {
        if (!seen.has(token)) {
          seen.add(token);
          calls.push(token);
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(body);
  return calls;
}

function lineOf(sourceFile, node) {
  const { line } = sourceFile.getLineAndCharacterOfPosition(
    node.getStart(sourceFile),
  );
  return line + 1;
}

function posixRel(root, filePath) {
  return path.relative(root, filePath).split(path.sep).join("/");
}

function addFunc(out, local, meta) {
  if (!local || out[local]) return;
  out[local] = meta;
}

function hasExportModifier(node) {
  return (
    Array.isArray(node.modifiers) &&
    node.modifiers.some((m) => m.kind === ts.SyntaxKind.ExportKeyword)
  );
}

function collectExports(sourceFile, root, filePath) {
  const names = new Set();
  const reexports = [];
  for (const stmt of sourceFile.statements) {
    if (ts.isFunctionDeclaration(stmt) && stmt.name && hasExportModifier(stmt)) {
      names.add(stmt.name.text);
    }
    if (ts.isClassDeclaration(stmt) && stmt.name && hasExportModifier(stmt)) {
      names.add(stmt.name.text);
    }
    if (ts.isVariableStatement(stmt) && hasExportModifier(stmt)) {
      for (const decl of stmt.declarationList.declarations) {
        if (ts.isIdentifier(decl.name)) names.add(decl.name.text);
      }
    }
    if (ts.isExportAssignment(stmt) && ts.isIdentifier(stmt.expression)) {
      names.add(stmt.expression.text);
    }
    if (
      ts.isExportDeclaration(stmt) &&
      stmt.exportClause &&
      ts.isNamedExports(stmt.exportClause)
    ) {
      const fromSpec =
        stmt.moduleSpecifier && ts.isStringLiteral(stmt.moduleSpecifier)
          ? stmt.moduleSpecifier.text
          : null;
      const resolved = fromSpec
        ? resolveMappedModule(root, filePath, fromSpec)
        : null;
      for (const el of stmt.exportClause.elements) {
        const exportName = el.name.text;
        const imported = el.propertyName ? el.propertyName.text : exportName;
        names.add(exportName);
        if (resolved) {
          reexports.push({
            name: exportName,
            imported,
            from: resolved,
          });
        }
      }
    }
  }
  const visit = (node) => {
    if (
      ts.isBinaryExpression(node) &&
      node.operatorToken.kind === ts.SyntaxKind.EqualsToken
    ) {
      const left = node.left;
      if (
        ts.isPropertyAccessExpression(left) &&
        ts.isIdentifier(left.expression) &&
        left.expression.text === "exports" &&
        ts.isIdentifier(left.name)
      ) {
        names.add(left.name.text);
      }
      if (
        ts.isPropertyAccessExpression(left) &&
        ts.isPropertyAccessExpression(left.expression) &&
        ts.isIdentifier(left.expression.expression) &&
        left.expression.expression.text === "module" &&
        ts.isIdentifier(left.expression.name) &&
        left.expression.name.text === "exports" &&
        ts.isObjectLiteralExpression(node.right)
      ) {
        for (const prop of node.right.properties) {
          if (ts.isShorthandPropertyAssignment(prop)) {
            names.add(prop.name.text);
          } else if (
            ts.isPropertyAssignment(prop) &&
            ts.isIdentifier(prop.name)
          ) {
            names.add(prop.name.text);
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return { names: [...names], reexports };
}

function tryFileCandidates(root, absBase) {
  const candidates = [
    absBase,
    absBase + ".js",
    absBase + ".mjs",
    absBase + ".cjs",
    absBase + ".ts",
    absBase + ".tsx",
    absBase + ".jsx",
    path.join(absBase, "index.js"),
    path.join(absBase, "index.ts"),
    path.join(absBase, "index.mjs"),
    path.join(absBase, "index.tsx"),
    path.join(absBase, "index.jsx"),
  ];
  const hits = [];
  const seen = new Set();
  for (const c of candidates) {
    const norm = path.resolve(c);
    if (seen.has(norm)) continue;
    seen.add(norm);
    if (fs.existsSync(norm) && fs.statSync(norm).isFile()) {
      hits.push(norm);
    }
  }
  if (hits.length !== 1) return null;
  return posixRel(root, hits[0]);
}

function resolveRelativeModule(root, fromFile, spec) {
  const base = path.resolve(path.dirname(fromFile), spec);
  const hit = tryFileCandidates(root, base);
  if (hit) return hit;
  // Wave 22: nearest package.json "exports" for relative subpaths only.
  const viaExports = resolveViaPackageExports(root, fromFile, spec);
  if (viaExports) return viaExports;
  return null;
}

/**
 * Wave 29: resolve non-relative specs via nearest package.json "imports"
 * and/or nearest tsconfig/jsconfig "paths" when the target file is unique.
 * Still parse-only — no typechecking, no node_modules invent.
 */
function resolveMappedModule(root, fromFile, spec) {
  if (!spec || typeof spec !== "string") return null;
  if (spec.startsWith("./") || spec.startsWith("../")) {
    return resolveRelativeModule(root, fromFile, spec);
  }
  // Bare relative without ./ is not supported (ambiguous with package names).
  if (spec.startsWith("#")) {
    return resolveViaPackageImports(root, fromFile, spec);
  }
  // tsconfig/jsconfig paths (e.g. @lib/foo); never bare npm registry packages.
  return resolveViaTsconfigPaths(root, fromFile, spec);
}

function findNearestConfig(root, fromFile, names) {
  const rootAbs = path.resolve(root);
  let dir = path.dirname(path.resolve(fromFile));
  while (true) {
    for (const name of names) {
      const cand = path.join(dir, name);
      if (fs.existsSync(cand) && fs.statSync(cand).isFile()) {
        return cand;
      }
    }
    if (path.resolve(dir) === rootAbs) break;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    if (!dir.startsWith(rootAbs) && dir !== rootAbs) break;
    dir = parent;
    if (
      !path.resolve(dir).startsWith(rootAbs) &&
      path.resolve(dir) !== rootAbs
    ) {
      break;
    }
  }
  return null;
}

/**
 * Nearest package.json "imports" (#internal, #lib/*, …) — unique file only.
 * Does not invent node_modules or conditional multi-target maps.
 */
function resolveViaPackageImports(root, fromFile, spec) {
  if (!spec.startsWith("#")) return null;
  const pkgJsonPath = findNearestConfig(root, fromFile, ["package.json"]);
  if (!pkgJsonPath) return null;
  let pkg;
  try {
    pkg = JSON.parse(fs.readFileSync(pkgJsonPath, "utf8"));
  } catch {
    return null;
  }
  if (!pkg || !pkg.imports || typeof pkg.imports !== "object") return null;
  const pkgDir = path.dirname(pkgJsonPath);
  const mapped = applyPathPatterns(pkg.imports, spec);
  if (!mapped || mapped.length === 0) return null;
  const hits = [];
  const seen = new Set();
  for (const target of mapped) {
    if (typeof target !== "string" || !target.startsWith("./")) continue;
    const abs = path.resolve(pkgDir, target);
    const rel = tryFileCandidates(root, abs);
    if (rel && !seen.has(rel)) {
      seen.add(rel);
      hits.push(rel);
    }
  }
  return hits.length === 1 ? hits[0] : null;
}

/**
 * Nearest tsconfig.json / jsconfig.json compilerOptions.paths (+ baseUrl).
 * Only exact / single-star patterns; omit when multiple patterns yield
 * distinct files. Does not merge ``extends`` and does not typecheck.
 */
function resolveViaTsconfigPaths(root, fromFile, spec) {
  const cfgPath = findNearestConfig(root, fromFile, [
    "tsconfig.json",
    "jsconfig.json",
  ]);
  if (!cfgPath) return null;
  let cfg;
  try {
    cfg = JSON.parse(stripJsonc(fs.readFileSync(cfgPath, "utf8")));
  } catch {
    return null;
  }
  const opts = (cfg && cfg.compilerOptions) || {};
  const paths = opts.paths;
  if (!paths || typeof paths !== "object") return null;
  const cfgDir = path.dirname(cfgPath);
  const baseUrl = opts.baseUrl
    ? path.resolve(cfgDir, String(opts.baseUrl))
    : cfgDir;
  const mapped = applyPathPatterns(paths, spec);
  if (!mapped || mapped.length === 0) return null;
  const hits = [];
  const seen = new Set();
  for (const target of mapped) {
    if (typeof target !== "string") continue;
    // Refuse escaping scan root via .. beyond baseUrl when under root.
    const abs = path.resolve(baseUrl, target);
    const rootAbs = path.resolve(root);
    if (!abs.startsWith(rootAbs) && abs !== rootAbs) continue;
    const rel = tryFileCandidates(root, abs);
    if (rel && !seen.has(rel)) {
      seen.add(rel);
      hits.push(rel);
    }
  }
  return hits.length === 1 ? hits[0] : null;
}

/** Best-effort strip of line and block comments for tsconfig JSONC. */
function stripJsonc(text) {
  let out = "";
  let i = 0;
  const n = text.length;
  while (i < n) {
    const ch = text[i];
    if (ch === '"' || ch === "'") {
      const quote = ch;
      out += ch;
      i += 1;
      while (i < n) {
        const c = text[i];
        out += c;
        i += 1;
        if (c === "\\" && i < n) {
          out += text[i];
          i += 1;
          continue;
        }
        if (c === quote) break;
      }
      continue;
    }
    if (ch === "/" && i + 1 < n && text[i + 1] === "/") {
      i += 2;
      while (i < n && text[i] !== "\n" && text[i] !== "\r") i += 1;
      continue;
    }
    if (ch === "/" && i + 1 < n && text[i + 1] === "*") {
      i += 2;
      while (i + 1 < n && !(text[i] === "*" && text[i + 1] === "/")) i += 1;
      i = Math.min(n, i + 2);
      continue;
    }
    out += ch;
    i += 1;
  }
  return out;
}

/**
 * Match Node/TS path-map patterns. Prefer longest pattern prefix when several
 * match; return candidate target strings (with ``*`` substituted).
 * Values may be a string or string[].
 */
function applyPathPatterns(mapField, spec) {
  const entries = [];
  for (const [pattern, raw] of Object.entries(mapField)) {
    if (typeof pattern !== "string") continue;
    const targets = Array.isArray(raw)
      ? raw.filter((t) => typeof t === "string")
      : typeof raw === "string"
        ? [raw]
        : typeof raw === "object" && raw !== null
          ? // Conditional import map: unique string only
            (() => {
              const s = unwrapExportValue(raw);
              return s ? [s] : [];
            })()
          : [];
    if (targets.length === 0) continue;
    const star = pattern.indexOf("*");
    if (star >= 0) {
      const prefix = pattern.slice(0, star);
      const suffix = pattern.slice(star + 1);
      if (
        spec.startsWith(prefix) &&
        spec.endsWith(suffix) &&
        spec.length >= prefix.length + suffix.length
      ) {
        const mid = spec.slice(prefix.length, spec.length - suffix.length);
        entries.push({
          pattern,
          prefixLen: prefix.length,
          targets: targets.map((t) => t.split("*").join(mid)),
        });
      }
    } else if (pattern === spec) {
      entries.push({ pattern, prefixLen: pattern.length, targets });
    }
  }
  if (entries.length === 0) return [];
  // Longest prefix wins (TypeScript-ish); if ties with different targets, fail closed.
  entries.sort((a, b) => b.prefixLen - a.prefixLen);
  const bestLen = entries[0].prefixLen;
  const best = entries.filter((e) => e.prefixLen === bestLen);
  const allTargets = [];
  const seen = new Set();
  for (const e of best) {
    for (const t of e.targets) {
      if (!seen.has(t)) {
        seen.add(t);
        allTargets.push(t);
      }
    }
  }
  // Multiple distinct pattern ties → ambiguous unless they share one target.
  if (best.length > 1 && allTargets.length > 1) return [];
  return allTargets;
}

/**
 * High-confidence package.json exports resolve (relative specs only).
 * Supports string exports, map entries, and a single conditional
 * (import/default/require/node) when exactly one string target exists.
 * Never invents bare package-name imports from node_modules.
 */
function resolveViaPackageExports(root, fromFile, spec) {
  if (!spec.startsWith("./") && !spec.startsWith("../")) return null;
  const rootAbs = path.resolve(root);
  let dir = path.dirname(path.resolve(fromFile));
  let pkgJsonPath = null;
  while (true) {
    const cand = path.join(dir, "package.json");
    if (fs.existsSync(cand) && fs.statSync(cand).isFile()) {
      pkgJsonPath = cand;
      break;
    }
    if (path.resolve(dir) === rootAbs) break;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    // Stay under scan root
    if (!dir.startsWith(rootAbs) && dir !== rootAbs) break;
    dir = parent;
    if (!path.resolve(dir).startsWith(rootAbs) && path.resolve(dir) !== rootAbs) {
      break;
    }
  }
  if (!pkgJsonPath) return null;
  let pkg;
  try {
    pkg = JSON.parse(fs.readFileSync(pkgJsonPath, "utf8"));
  } catch {
    return null;
  }
  if (!pkg || pkg.exports === undefined || pkg.exports === null) return null;
  const pkgDir = path.dirname(pkgJsonPath);
  // Normalize requested key relative to package root
  let relFromPkg;
  try {
    relFromPkg =
      "./" +
      path
        .relative(pkgDir, path.resolve(path.dirname(fromFile), spec))
        .split(path.sep)
        .join("/");
  } catch {
    return null;
  }
  if (relFromPkg.includes("..")) return null;
  const keysToTry = [spec, relFromPkg];
  if (relFromPkg === "./.") keysToTry.push(".");
  if (spec === ".") keysToTry.push(".");

  const target = pickExportsTarget(pkg.exports, keysToTry);
  if (!target || typeof target !== "string") return null;
  if (!target.startsWith("./")) return null;
  const abs = path.resolve(pkgDir, target);
  if (!fs.existsSync(abs) || !fs.statSync(abs).isFile()) {
    // Try with extensions
    for (const ext of [".js", ".mjs", ".cjs", ".ts", ".tsx", ""]) {
      const c = abs + (abs.endsWith(ext) ? "" : ext);
      if (ext && fs.existsSync(c) && fs.statSync(c).isFile()) {
        return posixRel(root, c);
      }
    }
    const idx = path.join(abs, "index.js");
    if (fs.existsSync(idx) && fs.statSync(idx).isFile()) {
      return posixRel(root, idx);
    }
    return null;
  }
  return posixRel(root, abs);
}

function pickExportsTarget(exportsField, keysToTry) {
  if (typeof exportsField === "string") {
    // Only applies to "." / package root
    if (keysToTry.some((k) => k === "." || k === "./" || k === "./.")) {
      return exportsField;
    }
    return null;
  }
  if (typeof exportsField !== "object" || Array.isArray(exportsField)) {
    return null;
  }
  for (const key of keysToTry) {
    if (key in exportsField) {
      return unwrapExportValue(exportsField[key]);
    }
  }
  // Exact subpath match with normalized ./foo
  for (const key of Object.keys(exportsField)) {
    for (const want of keysToTry) {
      if (key === want || key === want.replace(/^\.\//, "./")) {
        return unwrapExportValue(exportsField[key]);
      }
    }
  }
  return null;
}

function unwrapExportValue(val) {
  if (typeof val === "string") return val;
  if (!val || typeof val !== "object" || Array.isArray(val)) return null;
  // Conditional exports: prefer import, then default, require, node — only if string
  for (const k of ["import", "default", "require", "node"]) {
    if (typeof val[k] === "string") return val[k];
    if (val[k] && typeof val[k] === "object" && typeof val[k].default === "string") {
      return val[k].default;
    }
  }
  // Single string value in object → unique
  const strings = Object.values(val).filter((v) => typeof v === "string");
  if (strings.length === 1) return strings[0];
  return null;
}

function trackableSpecifier(spec, resolved) {
  if (spec.startsWith("./") || spec.startsWith("../") || spec.startsWith("#")) {
    return true;
  }
  // Non-relative aliases only when path-mapping uniquely resolved a file.
  return Boolean(resolved);
}

function collectRelativeImports(sourceFile, root, filePath) {
  const imports = [];
  for (const stmt of sourceFile.statements) {
    if (!ts.isImportDeclaration(stmt) || !stmt.moduleSpecifier) continue;
    if (!ts.isStringLiteral(stmt.moduleSpecifier)) continue;
    const spec = stmt.moduleSpecifier.text;
    const resolved = resolveMappedModule(root, filePath, spec);
    if (!trackableSpecifier(spec, resolved)) continue;
    const bindings = {};
    const clause = stmt.importClause;
    if (clause) {
      if (clause.name) bindings[clause.name.text] = "default";
      if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
        for (const el of clause.namedBindings.elements) {
          const local = el.name.text;
          const imported = el.propertyName ? el.propertyName.text : local;
          bindings[local] = imported;
        }
      }
    }
    imports.push({
      specifier: spec,
      resolved,
      bindings,
    });
  }
  const visit = (node) => {
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "require" &&
      node.arguments.length >= 1 &&
      ts.isStringLiteral(node.arguments[0])
    ) {
      const spec = node.arguments[0].text;
      const resolved = resolveMappedModule(root, filePath, spec);
      if (trackableSpecifier(spec, resolved)) {
        const parent = node.parent;
        const bindings = {};
        if (
          parent &&
          ts.isVariableDeclaration(parent) &&
          ts.isIdentifier(parent.name)
        ) {
          bindings[parent.name.text] = "*";
        }
        imports.push({
          specifier: spec,
          resolved,
          bindings,
        });
      }
    }
    ts.forEachChild(node, visit);
  };
  visit(sourceFile);
  return imports;
}

function parseFile(root, filePath) {
  const abs = path.isAbsolute(filePath) ? filePath : path.join(root, filePath);
  const text = fs.readFileSync(abs, "utf8");
  const rel = posixRel(root, abs);
  const sourceFile = ts.createSourceFile(
    abs,
    text,
    ts.ScriptTarget.Latest,
    true,
    scriptKindFor(abs),
  );
  const functions = {};
  const lang = languageFor(abs);

  const record = (local, node, body) => {
    const simple = local.includes(".") ? local.split(".").pop() : local;
    addFunc(functions, local, {
      file: rel,
      calls: extractCalls(body, simple),
      callers: [],
      complexity: decisionComplexity(body),
      side_effects: [],
      has_docstring: false,
      has_return_annotation: false,
      has_type_hints: false,
      typed_params: 0,
      total_params: 0,
      fully_typed_params: false,
      simple_name: simple,
      line: lineOf(sourceFile, node),
      analyzer: "javascript-ast",
      complexity_kind: "ast-cyclomatic",
      language: lang,
    });
  };

  for (const stmt of sourceFile.statements) {
    if (ts.isFunctionDeclaration(stmt) && stmt.name) {
      record(stmt.name.text, stmt, stmt.body || stmt);
    } else if (ts.isClassDeclaration(stmt) && stmt.name) {
      const cn = stmt.name.text;
      for (const member of stmt.members) {
        if (ts.isConstructorDeclaration(member)) {
          record(`${cn}.constructor`, member, member.body || member);
        } else if (
          (ts.isMethodDeclaration(member) ||
            ts.isGetAccessorDeclaration(member) ||
            ts.isSetAccessorDeclaration(member)) &&
          member.name &&
          ts.isIdentifier(member.name)
        ) {
          record(`${cn}.${member.name.text}`, member, member.body || member);
        }
      }
    } else if (ts.isVariableStatement(stmt)) {
      for (const decl of stmt.declarationList.declarations) {
        if (!ts.isIdentifier(decl.name) || !decl.initializer) continue;
        const init = decl.initializer;
        if (ts.isArrowFunction(init) || ts.isFunctionExpression(init)) {
          record(decl.name.text, decl, init.body || init);
        }
      }
    }
  }

  // Nested function declarations (first wins on name collision).
  const walkNested = (node) => {
    if (ts.isFunctionDeclaration(node) && node.name) {
      record(node.name.text, node, node.body || node);
    }
    ts.forEachChild(node, walkNested);
  };
  walkNested(sourceFile);

  const exportInfo = collectExports(sourceFile, root, abs);
  return {
    functions,
    exports: exportInfo.names,
    reexports: exportInfo.reexports,
    imports: collectRelativeImports(sourceFile, root, abs),
    file: rel,
  };
}

function main() {
  const raw = fs.readFileSync(0, "utf8");
  let req;
  try {
    req = JSON.parse(raw);
  } catch (e) {
    process.stdout.write(
      JSON.stringify({ ok: false, error: `invalid JSON request: ${e}` }),
    );
    process.exit(2);
  }
  const root = req.root;
  const files = Array.isArray(req.files) ? req.files : [];
  if (!root || typeof root !== "string") {
    process.stdout.write(JSON.stringify({ ok: false, error: "missing root" }));
    process.exit(2);
  }

  // Per-file results — local names must not be merged across files.
  const fileResults = [];

  for (const f of files) {
    const abs = path.isAbsolute(f) ? f : path.join(root, f);
    const ext = path.extname(abs).toLowerCase();
    if (!JS_LIKE.has(ext)) continue;
    if (!fs.existsSync(abs)) continue;
    try {
      const parsed = parseFile(root, abs);
      fileResults.push({
        file: parsed.file,
        functions: parsed.functions,
        exports: parsed.exports,
        reexports: parsed.reexports || [],
        imports: parsed.imports,
      });
    } catch (e) {
      process.stdout.write(
        JSON.stringify({
          ok: false,
          error: `parse failed for ${f}: ${e && e.message ? e.message : e}`,
        }),
      );
      process.exit(3);
    }
  }

  process.stdout.write(
    JSON.stringify({
      ok: true,
      analyzer: "javascript-ast",
      analyzer_fidelity: "ast",
      complexity_kind: "ast-cyclomatic",
      files: fileResults,
      complexity_formula:
        "1 + If/For/ForIn/ForOf/While/DoWhile/CaseClause/CatchClause/" +
        "ConditionalExpression/&&/|| in body; nested function bodies excluded",
    }),
  );
}

try {
  main();
} catch (e) {
  process.stdout.write(
    JSON.stringify({
      ok: false,
      error: e && e.message ? e.message : String(e),
    }),
  );
  process.exit(1);
}
