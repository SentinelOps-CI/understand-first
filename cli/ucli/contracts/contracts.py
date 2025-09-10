import os
import re
import importlib.util
import json
from typing import Tuple, Any, Dict, List
from collections import OrderedDict
import yaml
import re as _re

try:
    from openapi_schema_validator import validate as validate_openapi
except Exception:  # pragma: no cover
    validate_openapi = None  # type: ignore


def _read(path: str) -> str:
    return open(path, "r", encoding="utf-8", errors="ignore").read()


FN_DEF_RE = _re.compile(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\(", _re.M)
MODULE_LINE_RE = _re.compile(r"module:\s*(.+)")
FN_BLOCK_RE = _re.compile(
    r"^\s{2}([A-Za-z_][A-Za-z0-9_]*):([\s\S]*?)(?=^\s{2}[A-Za-z_]|^\S|\Z)",
    _re.M,
)
FN_HEAD_RE = _re.compile(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*):", _re.M)


def init_contracts(root: str) -> str:
    entries = []
    for r, d, files in os.walk(root):
        for f in files:
            if f.endswith(".py"):
                full = os.path.join(r, f)
                txt = _read(full)
                funcs = FN_DEF_RE.findall(txt)
                if not funcs:
                    continue
                section = [f"module: {full}", "functions:"]
                for fn in funcs:
                    section += [
                        f"  {fn}:",
                        "    pre: []",
                        "    post: []",
                        "    side_effects: []",
                    ]
                entries.append("\n".join(section))
    return "\n---\n".join(entries) + "\n"


def _exists_module_func(module_path: str, fn: str) -> bool:
    try:
        spec = importlib.util.spec_from_file_location("_mod", module_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore
        assert spec.loader is not None
        spec.loader.exec_module(mod)  # type: ignore
        return hasattr(mod, fn)
    except Exception:
        return False


def check_contracts(path: str) -> Tuple[bool, str]:
    txt = _read(path)
    ok = True
    report_lines = ["# Contracts Check Report\n"]
    blocks = [b.strip() for b in txt.split("\n---\n") if b.strip()]
    for b in blocks:
        m = MODULE_LINE_RE.search(b)
        if not m:
            ok = False
            report_lines.append("- Missing module line")
            continue
        mod = m.group(1).strip()
        for fn in FN_HEAD_RE.findall(b):
            exists = _exists_module_func(mod, fn)
            if not exists:
                ok = False
                report_lines.append(f"- [!] {mod}:{fn} not found")
            else:
                report_lines.append(f"- [ok] {mod}:{fn}")
    return ok, "\n".join(report_lines)


def _strategy_expr(meta: Dict[str, Any]) -> str:
    t = (meta or {}).get("type")
    if "enum" in (meta or {}):
        return "st.sampled_from(" + json.dumps(meta["enum"]) + ")"
    if t == "integer":
        args = []
        if "minimum" in meta:
            args.append(f"min_value={meta['minimum']}")
        if "maximum" in meta:
            args.append(f"max_value={meta['maximum']}")
        return "st.integers(" + ", ".join(args) + ")"
    if t == "number":
        args = ["allow_nan=False", "allow_infinity=False"]
        if "minimum" in meta:
            args.append(f"min_value={meta['minimum']}")
        if "maximum" in meta:
            args.append(f"max_value={meta['maximum']}")
        return "st.floats(" + ", ".join(args) + ")"
    if t == "string":
        if "pattern" in meta and isinstance(meta["pattern"], str):
            pat = meta["pattern"].replace("\\", r"\\").replace('"', r"\"")
            return f'st.from_regex("{pat}")'
        args = []
        if "minLength" in meta:
            args.append(f"min_size={meta['minLength']}")
        if "maxLength" in meta:
            args.append(f"max_size={meta['maxLength']}")
        return "st.text(" + ", ".join(args) + ")"
    if t == "array":
        item_expr = _strategy_expr((meta or {}).get("items") or {})
        args = [item_expr]
        if "minItems" in meta:
            args.append(f"min_size={meta['minItems']}")
        if "maxItems" in meta:
            args.append(f"max_size={meta['maxItems']}")
        return "st.lists(" + ", ".join(args) + ")"
    if t == "object":
        props = (meta or {}).get("properties") or {}
        parts = []
        for k, v in props.items():
            parts.append(f'"{k}": ' + _strategy_expr(v))
        return "st.fixed_dictionaries({" + ", ".join(parts) + "})"
    return "st.none()"


def stub_tests(path: str) -> str:
    txt = _read(path)
    out = [
        "# Auto-generated contract stubs\n",
        "# Requires: hypothesis\n",
        "from hypothesis import strategies as st\n",
        "import importlib.util\n",
    ]
    idx = 0
    blocks = [b.strip() for b in txt.split("\n---\n") if b.strip()]
    for b in blocks:
        m = re.search(r"module:\s*(.+)", b)
        if not m:
            continue
        mod = m.group(1).strip().replace("\\", "/")
        is_virtual = mod.startswith(("ROUTE::", "PROTO::"))
        if not is_virtual:
            spec_line = (
                "spec = importlib.util.spec_from_file_location(" f"'m_{idx}', '{mod}')"
            )
            out.append(spec_line)
            out.append(f"m_{idx} = importlib.util.module_from_spec(spec)")
            out.append(f"spec.loader.exec_module(m_{idx})  # type: ignore\n")
        for fn_block in FN_BLOCK_RE.finditer(b):
            fn = fn_block.group(1)
            body = fn_block.group(2)
            req_m = re.search(r"request_meta:\s*(\{.*\})", body)
            resp_m = re.search(r"response_meta:\s*(\{.*\})", body)
            if req_m:
                try:
                    meta = json.loads(req_m.group(1))
                    expr = _strategy_expr(meta)
                    out.append(f"req_strategy_{idx}_{fn} = {expr}")
                except Exception:
                    pass
            if resp_m:
                try:
                    meta = json.loads(resp_m.group(1))
                    expr = _strategy_expr(meta)
                    out.append(f"resp_strategy_{idx}_{fn} = {expr}")
                except Exception:
                    pass
            if not is_virtual:
                out.append(
                    (
                        f"def test_{idx}_{fn}():\n"
                        f"    # TODO: fill inputs;\n"
                        f"    # assert pre/post conditions\n"
                        f"    assert hasattr(m_{idx}, '{fn}')\n"
                    )
                )
        idx += 1
    return "\n".join(out) + "\n"


def _sanitize_identifier(s: str) -> str:
    # Keep letters, digits, underscore; collapse repeats; strip edges
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s)
    return s.strip("_")


def _choose_2xx_response(op: Dict[str, Any]) -> Dict[str, Any]:
    responses = op.get("responses") or {}
    if not isinstance(responses, dict):
        return {}
    codes = sorted([c for c in responses.keys() if str(c).startswith("2")])
    for code in ["200", "201", "202", "204"]:
        if code in responses:
            return responses.get(code) or {}
    if codes:
        return responses.get(codes[0]) or {}
    return {}


def from_openapi(openapi_path: str) -> str:
    data_txt = _read(openapi_path)
    try:
        data = yaml.safe_load(data_txt) or {}
    except Exception:
        return ""
    # optional validation (non-fatal)
    try:
        if validate_openapi is not None:
            validate_openapi(data)
    except Exception:
        pass
    paths = (data or {}).get("paths", {}) or {}
    # components not currently used

    def extract_schema_meta(schema: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(schema, dict):
            return {}
        out: Dict[str, Any] = {}
        for k in [
            "type",
            "format",
            "enum",
            "minimum",
            "maximum",
            "pattern",
            "minLength",
            "maxLength",
            "items",
            "properties",
            "required",
            "minItems",
            "maxItems",
        ]:
            if k in schema:
                out[k] = schema[k]
        return out

    blocks = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        verbs = [v for v in ["get", "post", "put", "delete", "patch"] if v in path_item]
        if not verbs:
            continue
        section = [f"module: ROUTE::{path}", "functions:"]
        seen_fns = set()
        for v in verbs:
            op = path_item.get(v, {}) or {}
            raw_name = op.get("operationId") or f"{v}_{path.strip('/')}"
            # Replace path params like {id} with id
            raw_name = re.sub(r"\{([^}]+)\}", r"\1", raw_name)
            name = _sanitize_identifier(raw_name)
            if name in seen_fns:
                # Ensure uniqueness if duplicates encountered
                suffix = 2
                while f"{name}_{suffix}" in seen_fns:
                    suffix += 1
                name = f"{name}_{suffix}"
            seen_fns.add(name)
            section += [
                f"  {name}:",
                "    pre: []",
                "    post: []",
                "    side_effects: []",
            ]
            # attach meta as comments-like YAML keys
            # requestBody schema
            req_content = (op.get("requestBody") or {}).get("content") or {}
            app_json_req = req_content.get("application/json") or {}
            req_schema = app_json_req.get("schema") or {}

            chosen_resp = _choose_2xx_response(op)
            resp_content = chosen_resp.get("content") or {}
            app_json_resp = resp_content.get("application/json") or {}
            resp_schema = app_json_resp.get("schema", {})
            req_meta = extract_schema_meta(req_schema)
            resp_meta = extract_schema_meta(resp_schema)
            if req_meta:
                req_meta_txt = json.dumps(req_meta, separators=(",", ":"))
                section.append("    request_meta: " + req_meta_txt)
            if resp_meta:
                resp_meta_txt = json.dumps(resp_meta, separators=(",", ":"))
                section.append("    response_meta: " + resp_meta_txt)
        blocks.append("\n".join(section))
    return "\n---\n".join(blocks) + ("\n" if blocks else "")


def from_proto(proto_path: str) -> str:
    txt = _read(proto_path)
    rpcs = re.findall(r"rpc\s+(\w+)\s*\(", txt)
    if not rpcs:
        return ""
    try:
        rel = os.path.relpath(proto_path)
    except Exception:
        rel = proto_path
    rel = rel.replace("\\", "/")
    section = [f"module: PROTO::{rel}", "functions:"]
    for r in rpcs:
        section += [
            f"  {r}:",
            "    pre: []",
            "    post: []",
            "    side_effects: []",
        ]
    return "\n".join(section) + "\n"


def lean_stubs(contracts_yaml: str, out_dir: str) -> int:
    txt = _read(contracts_yaml)
    blocks = [b.strip() for b in txt.split("\n---\n") if b.strip()]
    count = 0
    for b in blocks:
        header = [
            "import Std.Data",
            f"-- auto-generated from {contracts_yaml}",
            "namespace Contracts\n",
        ]
        mod_m = re.search(r"module:\s*(.+)", b)
        raw_mod = mod_m.group(1).strip() if mod_m else "Module"
        mod_name = _sanitize_identifier(
            raw_mod.replace("::", "__").replace("/", "_").replace("\\", "_")
        )
        lines = list(header)
        for fn_block in FN_BLOCK_RE.finditer(b):
            fn = _sanitize_identifier(fn_block.group(1))
            lines.append(f"def invariant_{mod_name}__{fn} : Prop := True\n")
            theorem_sig = (
                f"theorem invariant_{mod_name}__{fn}_holds : "
                f"invariant_{mod_name}__{fn} := by trivial\n"
            )
            lines.append(theorem_sig)
        fname = os.path.join(out_dir, f"invariants_{mod_name}.lean")
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\\n".join(lines))
        count += 1
    return count


def _parse_blocks(txt: str):
    return [b.strip() for b in txt.split("\n---\n") if b.strip()]


def report_json(path: str):
    txt = _read(path)
    issues = []
    blocks = _parse_blocks(txt)
    for b in blocks:
        m = MODULE_LINE_RE.search(b)
        mod = m.group(1).strip() if m else ""
        for fn in FN_HEAD_RE.findall(b):
            exists = (
                _exists_module_func(mod, fn)
                if mod and not mod.startswith(("ROUTE::", "PROTO::"))
                else True
            )
            if not exists:
                issues.append(
                    {
                        "module_path": mod,
                        "function": fn,
                        "message": f"{mod}:{fn} not found",
                        "severity": "error",
                    }
                )
    return {"issues": issues}


def compose(paths: List[str]) -> str:
    """Compose multiple contract YAML files into a single YAML string.
    Keeps first occurrence order; de-duplicates functions per module by name.
    """
    module_to_fns = OrderedDict()
    modules_order: List[str] = []
    for p in paths:
        try:
            txt = _read(p)
        except Exception:
            continue
        for b in _parse_blocks(txt):
            m = re.search(r"module:\s*(.+)", b)
            if not m:
                # skip invalid block
                continue
            mod = m.group(1).strip()
            if mod not in module_to_fns:
                module_to_fns[mod] = OrderedDict()
                modules_order.append(mod)
            fn_map = module_to_fns[mod]
            for fn_block in FN_BLOCK_RE.finditer(b):
                fn = fn_block.group(1)
                body = fn_block.group(2)
                if fn not in fn_map:
                    # Store exact body including newlines/indentation
                    fn_map[fn] = [f"  {fn}:"] + [
                        line for line in body.splitlines() if line.strip()
                    ]
                # else: duplicate; keep first
    sections: List[str] = []
    for mod in modules_order:
        parts = [f"module: {mod}", "functions:"]
        for fn, lines in module_to_fns[mod].items():
            parts.extend(lines)
        sections.append("\n".join(parts))
    return ("\n---\n".join(sections) + "\n") if sections else ""


def verify_lean(contracts_yaml: str, lean_dir: str) -> Dict[str, Any]:
    """Verify that Lean stubs exist for each function in contracts.
    Returns a JSON-serializable summary; does not attempt to compile Lean.
    """
    txt = _read(contracts_yaml)
    blocks = _parse_blocks(txt)
    expected: List[str] = []
    for b in blocks:
        mod_m = re.search(r"module:\s*(.+)", b)
        raw_mod = mod_m.group(1).strip() if mod_m else "Module"
        mod_name = _sanitize_identifier(
            raw_mod.replace("::", "__").replace("/", "_").replace("\\", "_")
        )
        for fn_m in re.finditer(
            r"^\s{2}([A-Za-z_][A-Za-z0-9_]*):",
            b,
            re.M,
        ):
            fn = _sanitize_identifier(fn_m.group(1))
            expected.append(f"theorem invariant_{mod_name}__{fn}_holds")
    found: List[str] = []
    try:
        for r, _, files in os.walk(lean_dir):
            for f in files:
                if not f.endswith(".lean"):
                    continue
                content = _read(os.path.join(r, f))
                for e in expected:
                    if e in content:
                        found.append(e)
    except Exception:
        pass
    missing = [e for e in expected if e not in set(found)]
    return {
        "modules_total": len(blocks),
        "functions_total": len(expected),
        "invariants_found": len(set(found)),
        "missing_invariants": missing,
    }
