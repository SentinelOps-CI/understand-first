from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import sqlite3
import time
from multiprocessing import Pool, cpu_count
from typing import Any

# ---------------------------------------------------------------------------
# Side-effect heuristics (high-confidence AST signals — NOT perfect analysis)
#
# Emitted tags (sorted unique list per function):
#   writes_global      – assignment to a name declared global/nonlocal
#   writes_attribute   – store to an attribute (e.g. self.x = ..., obj.y = ...)
#   io_open            – call to builtin open(...)
#   io_print           – call to print(...)
#   io_write           – .write / .writelines call
#   io_read            – .read / .readline / .readlines call
#   network_call       – local call whose callee looks like HTTP/socket I/O
#                        (Name in NETWORK_BARE, or Attribute on NETWORK_ROOTS)
#   logging            – logging.* or *.info/debug/warning/error/exception/critical
#
# False positives are acceptable when documented; absence of a tag never means
# "proven pure". Nested FunctionDef / AsyncFunctionDef / ClassDef bodies are
# attributed to the nested definition, not the enclosing function.
# ---------------------------------------------------------------------------

_NETWORK_ROOTS = frozenset({"requests", "httpx", "urllib", "aiohttp", "socket", "http", "urllib3"})
_NETWORK_BARE = frozenset(
    {"urlopen", "urlretrieve", "urlfetch", "get", "post", "put", "patch", "delete"}
)
# Bare get/post are too ambiguous alone; only treat Attribute forms for those.
_NETWORK_BARE_STRICT = frozenset({"urlopen", "urlretrieve", "urlfetch"})
_IO_WRITE_ATTRS = frozenset({"write", "writelines"})
_IO_READ_ATTRS = frozenset({"read", "readline", "readlines"})
_LOG_ATTRS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
)


def _is_code_file(path: pathlib.Path) -> bool:
    return path.suffix == ".py" and not any(part.startswith(".") for part in path.parts)


def _file_signature(path: pathlib.Path) -> tuple[int, int, str]:
    st = path.stat()
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    return int(st.st_mtime), int(st.st_size), h


def _cyclomatic_complexity(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """McCabe-style cyclomatic complexity for a single function (nested defs excluded).

    Formula:
      CC = 1
         + each If / IfExp / For / AsyncFor / While / Assert
         + each ExceptHandler
         + each extra Boolean operator in And/Or  (len(values) - 1)
         + each ``if`` filter in a comprehension / generator expression
         + each ``match`` case (ast.Match)

    Nested FunctionDef / AsyncFunctionDef / ClassDef bodies are skipped so their
    decisions are not attributed to the enclosing function.
    """
    score = 1

    class _CCVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            # Nested function: do not descend.
            return

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_If(self, node: ast.If) -> None:
            nonlocal score
            score += 1
            self.generic_visit(node)

        def visit_IfExp(self, node: ast.IfExp) -> None:
            nonlocal score
            score += 1
            self.generic_visit(node)

        def visit_For(self, node: ast.For) -> None:
            nonlocal score
            score += 1
            self.generic_visit(node)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            nonlocal score
            score += 1
            self.generic_visit(node)

        def visit_While(self, node: ast.While) -> None:
            nonlocal score
            score += 1
            self.generic_visit(node)

        def visit_Assert(self, node: ast.Assert) -> None:
            nonlocal score
            score += 1
            self.generic_visit(node)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            nonlocal score
            score += 1
            self.generic_visit(node)

        def visit_BoolOp(self, node: ast.BoolOp) -> None:
            nonlocal score
            score += max(0, len(node.values) - 1)
            self.generic_visit(node)

        def visit_comprehension(self, node: ast.comprehension) -> None:
            nonlocal score
            score += len(node.ifs)
            self.generic_visit(node)

        def visit_Match(self, node: ast.AST) -> None:
            # match/case (3.10+); typed as AST so pyright stays clean on 3.9.
            nonlocal score
            cases = getattr(node, "cases", None) or []
            score += len(cases)
            self.generic_visit(node)

    visitor = _CCVisitor()
    for stmt in func_node.body:
        visitor.visit(stmt)
    return score


def _side_effects_for_func(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Return sorted heuristic side-effect tags for one function body."""
    effects: set[str] = set()
    external_names: set[str] = set()

    class _SEVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_Global(self, node: ast.Global) -> None:
            external_names.update(node.names)

        def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
            external_names.update(node.names)

        def _mark_store(self, target: ast.AST) -> None:
            if isinstance(target, ast.Name):
                if target.id in external_names:
                    effects.add("writes_global")
            elif isinstance(target, ast.Attribute):
                effects.add("writes_attribute")
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    self._mark_store(elt)
            elif isinstance(target, ast.Starred):
                self._mark_store(target.value)

        def visit_Assign(self, node: ast.Assign) -> None:
            for t in node.targets:
                self._mark_store(t)
            self.generic_visit(node)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            self._mark_store(node.target)
            self.generic_visit(node)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if node.value is not None:
                self._mark_store(node.target)
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            if isinstance(func, ast.Name):
                name = func.id
                if name == "open":
                    effects.add("io_open")
                elif name == "print":
                    effects.add("io_print")
                elif name in _NETWORK_BARE_STRICT:
                    effects.add("network_call")
            elif isinstance(func, ast.Attribute):
                attr = func.attr
                if attr in _IO_WRITE_ATTRS:
                    effects.add("io_write")
                elif attr in _IO_READ_ATTRS:
                    effects.add("io_read")
                if attr in _LOG_ATTRS:
                    effects.add("logging")
                # requests.get / httpx.post / socket.create_connection
                root = func.value
                if isinstance(root, ast.Name) and root.id in _NETWORK_ROOTS:
                    effects.add("network_call")
                elif isinstance(root, ast.Attribute) and root.attr in _NETWORK_ROOTS:
                    effects.add("network_call")
            self.generic_visit(node)

    visitor = _SEVisitor()
    for stmt in func_node.body:
        visitor.visit(stmt)
    return sorted(effects)


def _annotation_present(node: ast.AST | None) -> bool:
    return node is not None


def _func_type_hint_flags(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    """Simple AST type-hint / docstring gap signals (not full typing fidelity)."""
    args = list(node.args.args) + list(node.args.kwonlyargs)
    if node.args.vararg is not None:
        args.append(node.args.vararg)
    if node.args.kwarg is not None:
        args.append(node.args.kwarg)
    typed_params = sum(1 for a in args if _annotation_present(a.annotation))
    total_params = len(args)
    has_return = _annotation_present(node.returns)
    return {
        "has_docstring": ast.get_docstring(node) is not None,
        "has_return_annotation": has_return,
        "has_type_hints": has_return or typed_params > 0,
        "typed_params": typed_params,
        "total_params": total_params,
        # True when every named param (including self) has an annotation, or there are none.
        "fully_typed_params": total_params == 0 or typed_params == total_params,
    }


def _package_parts_for_file(file_path: pathlib.Path) -> list[str]:
    """Infer package parts by walking up directories that contain ``__init__.py``.

    Namespace packages without ``__init__.py`` are not inferred (no invented edges).
    """
    parts: list[str] = []
    try:
        cur = file_path.resolve().parent
    except OSError:
        cur = file_path.parent
    while True:
        if not (cur / "__init__.py").is_file():
            break
        parts.append(cur.name)
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
    parts.reverse()
    return parts


def _resolve_relative_module(file_path: pathlib.Path, module: str | None, level: int) -> str | None:
    """Resolve a relative ``from`` import to a dotted module path, or None if invalid.

    High-confidence only: refuses imports that climb above the inferred package root.
    """
    if level <= 0:
        return module
    pkg_parts = _package_parts_for_file(file_path)
    # level=1 stays in current package; level=2 goes to parent, etc.
    up = level - 1
    if up > len(pkg_parts):
        return None
    base_parts = pkg_parts[: len(pkg_parts) - up] if up else list(pkg_parts)
    if module:
        mod_parts = [p for p in module.split(".") if p]
        return ".".join(base_parts + mod_parts) if (base_parts or mod_parts) else None
    return ".".join(base_parts) if base_parts else None


def _is_type_checking_expr(node: ast.AST) -> bool:
    """True for ``TYPE_CHECKING`` / ``typing.TYPE_CHECKING`` (and extensions)."""
    if isinstance(node, ast.Name) and node.id == "TYPE_CHECKING":
        return True
    if isinstance(node, ast.Attribute) and node.attr == "TYPE_CHECKING":
        return True
    return False


def _record_import_node(
    node: ast.AST,
    file_path: pathlib.Path,
    aliases: dict[str, str],
) -> None:
    """Record one Import / ImportFrom into ``aliases`` (mutates in place)."""
    if isinstance(node, ast.ImportFrom):
        if node.level and node.level > 0:
            base = _resolve_relative_module(file_path, node.module, node.level)
            if not base:
                return
        elif node.module is None:
            return
        else:
            base = node.module
        for alias in node.names:
            local = alias.asname or alias.name
            if alias.name == "*":
                continue
            # from pkg.mod import func -> local name maps to pkg.mod:func candidate key
            aliases[local] = f"{base}:{alias.name}"
    elif isinstance(node, ast.Import):
        for alias in node.names:
            local = alias.asname or alias.name.split(".")[-1]
            aliases[local] = alias.name


def _collect_import_aliases(tree: ast.AST, file_path: pathlib.Path) -> dict[str, str]:
    """Map local alias -> module path fragment for high-confidence import resolution.

    Records ``from X import Y`` / ``from X import Y as Z`` where Y is a plain name.
    Relative imports (``from .X import Y``, ``from .. import Y``) are resolved against
    ``file_path``'s package parts when confidence is unambiguous.
    Absolute ``import pkg.mod`` aliases are recorded as ``alias -> pkg.mod``.

    ``from``-import bindings use ``base:name`` so later resolution can distinguish
    symbol imports (``from mod import fn``) from module imports
    (``from pkg import mod`` → treat ``mod`` as submodule ``pkg.mod`` when a
    scanned module uniquely matches).

    Wave 30: also records imports under ``if TYPE_CHECKING:`` /
    ``if typing.TYPE_CHECKING:`` bodies (string annotations commonly pair with
    these). ``if not TYPE_CHECKING:`` bodies are ignored.
    """
    aliases: dict[str, str] = {}

    def walk_stmts(stmts: list[ast.stmt]) -> None:
        for node in stmts:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                _record_import_node(node, file_path, aliases)
            elif isinstance(node, ast.If) and _is_type_checking_expr(node.test):
                walk_stmts(list(node.body))
            # Do not walk unrelated If/try bodies — runtime-only imports stay opaque.

    walk_stmts(list(getattr(tree, "body", []) or []))
    return aliases


def _attr_call_token(node: ast.Attribute) -> str:
    """Serialize an attribute call target to a dotted token when rooted at a Name.

    ``mod.fn`` → ``mod.fn``; ``pkg.mod.fn`` → ``pkg.mod.fn``.
    Non-Name roots (``foo().bar``, ``self.x.y``) return the terminal attr only so
    we never invent a dotted chain we cannot resolve honestly.
    """
    parts: list[str] = []
    cur: ast.AST = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        parts.reverse()
        return ".".join(parts)
    return node.attr


# Names that are never treated as concrete class types for call resolution.
_NON_CLASS_TYPE_NAMES = frozenset(
    {
        "Any",
        "object",
        "None",
        "True",
        "False",
        "Ellipsis",
        "type",
        "Callable",
        "Literal",
        "TypedDict",
        "Protocol",
        "TypeVar",
        "Generic",
        "ClassVar",
        "Final",
        "Self",
        "Annotated",
        "Optional",
        "Union",
        "Required",
        "NotRequired",
        "str",
        "int",
        "float",
        "bool",
        "bytes",
        "list",
        "dict",
        "set",
        "tuple",
        "frozenset",
    }
)

# Subscript wrappers that unwrap to a single concrete type (Wave 30).
_TYPE_UNWRAP_SINGLE = frozenset({"Annotated", "Final", "ClassVar", "Required", "NotRequired"})
_TYPE_UNWRAP_OPTIONAL_UNION = frozenset({"Optional", "Union"})
_TYPE_UNWRAP_ALL = _TYPE_UNWRAP_SINGLE | _TYPE_UNWRAP_OPTIONAL_UNION
_TYPING_MODULES = frozenset({"typing", "typing_extensions"})


def _ast_from_annotation_string(text: str) -> ast.AST | None:
    """Parse a quoted annotation string into an expression AST, or None."""
    s = text.strip()
    if not s:
        return None
    try:
        return ast.parse(s, mode="eval").body
    except SyntaxError:
        return None


def _typing_wrapper_kind(
    node: ast.AST | None,
    aliases: dict[str, str] | None = None,
) -> str | None:
    """Return Optional/Union/Annotated/... when ``node`` is a typing wrapper.

    Recognizes bare names, ``typing.X`` / ``typing_extensions.X``, and
    ``from typing import Optional as Opt`` aliases (import-gated to typing*).
    """
    if node is None:
        return None
    if isinstance(node, ast.Name):
        name = node.id
        if aliases:
            binding = aliases.get(name)
            if binding is not None and ":" in binding:
                mod, imported = binding.rsplit(":", 1)
                if imported in _TYPE_UNWRAP_ALL and (not mod or mod in _TYPING_MODULES):
                    return imported
        if name in _TYPE_UNWRAP_ALL:
            return name
        return None
    if isinstance(node, ast.Attribute) and node.attr in _TYPE_UNWRAP_ALL:
        # Only typing / typing_extensions (or an alias to those modules).
        root = node.value
        if isinstance(root, ast.Name):
            if root.id in _TYPING_MODULES:
                return node.attr
            if aliases and aliases.get(root.id) in _TYPING_MODULES:
                return node.attr
            return None
        if isinstance(root, ast.Attribute) and root.attr in _TYPING_MODULES:
            return node.attr
        return None
    return None


def _simple_type_name(
    node: ast.AST | None,
    aliases: dict[str, str] | None = None,
) -> str | None:
    """High-confidence concrete class name from an annotation or constructor call.

    Accepts bare ``Foo``, ``pkg.Foo``, quoted ``\"Foo\"`` / ``\"Foo | None\"``,
    and wrappers ``Optional`` / ``Union`` / ``Annotated`` / ``Final`` /
    ``ClassVar`` (including ``typing.X`` and ``from typing import X as Y``)
    when exactly one non-None concrete name remains. Rejects multi-class
    unions, containers (``list[Foo]``), ``TypedDict`` / ``Protocol`` /
    builtins / ``Any`` — never invents a type.
    """
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        if node.value is None:
            return None
        if isinstance(node.value, str):
            inner = _ast_from_annotation_string(node.value)
            # Recurse without re-entering string mode on nested metadata.
            return _simple_type_name(inner, aliases) if inner is not None else None
        return None
    if isinstance(node, ast.Name):
        if node.id in _NON_CLASS_TYPE_NAMES:
            return None
        return node.id
    if isinstance(node, ast.Attribute):
        # pkg.Foo → Foo (local Class.method resolve uses the terminal name)
        if node.attr in _NON_CLASS_TYPE_NAMES:
            return None
        return node.attr
    if isinstance(node, ast.Subscript):
        kind = _typing_wrapper_kind(node.value, aliases)
        if kind in _TYPE_UNWRAP_OPTIONAL_UNION or kind in _TYPE_UNWRAP_SINGLE:
            return _unique_concrete_type(node.slice, aliases)
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _unique_concrete_type(node, aliases)
    if isinstance(node, ast.Tuple):
        return _unique_concrete_type(node, aliases)
    return None


def _unique_concrete_type(
    node: ast.AST | None,
    aliases: dict[str, str] | None = None,
) -> str | None:
    """Return a class name only when exactly one concrete type appears."""
    names: list[str] = []

    def walk(n: ast.AST | None) -> None:
        if n is None:
            return
        # Skip None and Annotated metadata string constants (not types).
        if isinstance(n, ast.Constant):
            return
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
            walk(n.left)
            walk(n.right)
            return
        if isinstance(n, ast.Tuple):
            for elt in n.elts:
                walk(elt)
            return
        # Nested Optional/Union/Annotated — unwrap rather than treating as class.
        if isinstance(n, ast.Subscript):
            kind = _typing_wrapper_kind(n.value, aliases)
            if kind in _TYPE_UNWRAP_ALL:
                walk(n.slice)
                return
        name = _simple_type_name(n, aliases)
        if name and name not in _TYPE_UNWRAP_ALL:
            names.append(name)

    walk(node)
    uniq = list(dict.fromkeys(names))
    if len(uniq) == 1:
        return uniq[0]
    return None


def _looks_like_class_name(name: str) -> bool:
    """PEP8 CapWords heuristic — snake_case calls are factories, not constructors."""
    return bool(name) and name[0].isupper() and name not in _NON_CLASS_TYPE_NAMES


def _constructor_type_name(node: ast.AST | None) -> str | None:
    """Class name from ``Foo(...)`` / ``pkg.Foo(...)`` CapWords call expressions only.

    Snake_case ``make()`` is *not* treated as a constructor — those bind via
    return-type propagation when the callee uniquely returns a concrete class.
    """
    if not isinstance(node, ast.Call):
        return None
    name = _simple_type_name(node.func)
    if name is None or not _looks_like_class_name(name):
        return None
    return name


def _factory_call_callee(node: ast.AST | None) -> str | None:
    """Callee token for ``name = factory(...)`` when not a CapWords constructor."""
    if not isinstance(node, ast.Call):
        return None
    if _constructor_type_name(node) is not None:
        return None
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return _attr_call_token(node.func)
    return None


def _module_path_from_file(file_path: str) -> str:
    """Best-effort dotted module path from a scanned file path (no package inventing)."""
    posix = file_path.replace("\\", "/").removesuffix(".py")
    if posix.endswith("/__init__"):
        posix = posix[: -len("/__init__")]
    return posix.replace("/", ".")


def _resolve_class_attr_in_file(
    class_name: str,
    attr: str,
    origin_file: str,
    by_short: dict[str, list[str]],
    functions: dict[str, Any],
) -> list[str]:
    """Unique ``Class.attr`` defined in ``origin_file``, else []."""
    local_key = f"{class_name}.{attr}"
    candidates = [
        qn
        for qn in dict.fromkeys(by_short.get(local_key, []))
        if qn.rsplit(":", 1)[-1] == local_key and functions[qn].get("file") == origin_file
    ]
    if len(candidates) == 1:
        return candidates
    return []


def _canonicalize_type_via_imports(
    name: str,
    aliases: dict[str, str],
) -> tuple[str, str | None]:
    """Map a local type name to ``(ClassName, origin_mod)`` via import aliases.

    ``from models import Foo as F`` → aliases ``F`` = ``models:Foo`` yields
    ``(\"Foo\", \"models\")``. Bare names without a class import stay unchanged.
    """
    binding = aliases.get(name)
    if binding is not None and ":" in binding:
        mod, imported = binding.rsplit(":", 1)
        if _looks_like_class_name(imported):
            return imported, mod or None
        if _looks_like_class_name(name):
            return name, mod or None
    return name, None


def _module_path_for_attr_value(
    value: ast.AST,
    aliases: dict[str, str],
) -> str | None:
    """Dotted module path for the root of ``models.Foo`` / ``pkg.mod.Foo``."""
    parts: list[str] = []
    cur: ast.AST = value
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.append(cur.id)
    parts.reverse()
    root = parts[0]
    rest = parts[1:]
    binding = aliases.get(root)
    if binding is None:
        return None
    if ":" not in binding:
        return ".".join([binding, *rest]) if rest else binding
    base, imported = binding.rsplit(":", 1)
    mod = f"{base}.{imported}" if base else imported
    return ".".join([mod, *rest]) if rest else mod


def _type_ref_with_origin(
    node: ast.AST | None,
    aliases: dict[str, str],
) -> tuple[str | None, str | None]:
    """``(ClassName, origin_mod|None)`` from an annotation or constructor target.

    Origin is a dotted module when the type is import-aliased (``Foo`` /
    ``F`` / ``models.Foo``). Optional/Union/Annotated/Final/ClassVar wrappers
    keep a single concrete name; multi-class forms return ``(None, None)``.
    Quoted annotations are parsed and re-entered.
    """
    if node is None:
        return None, None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        inner = _ast_from_annotation_string(node.value)
        return _type_ref_with_origin(inner, aliases) if inner is not None else (None, None)
    if isinstance(node, ast.Call):
        # CapWords constructor — origin from the callee expression.
        if _constructor_type_name(node) is None:
            return None, None
        return _type_ref_with_origin(node.func, aliases)
    if isinstance(node, ast.Name):
        if node.id in _NON_CLASS_TYPE_NAMES:
            return None, None
        return _canonicalize_type_via_imports(node.id, aliases)
    if isinstance(node, ast.Attribute):
        if node.attr in _NON_CLASS_TYPE_NAMES:
            return None, None
        # typing.Optional is a wrapper, not a class — handled via Subscript.
        if _typing_wrapper_kind(node, aliases):
            return None, None
        mod = _module_path_for_attr_value(node.value, aliases)
        return node.attr, mod
    if isinstance(node, ast.Subscript):
        kind = _typing_wrapper_kind(node.value, aliases)
        if kind in _TYPE_UNWRAP_ALL:
            inner = _unique_concrete_type(node.slice, aliases)
            if not inner:
                return None, None
            # Prefer Attribute/Name origin inside the slice when unique.
            return _type_ref_with_origin_for_name(node.slice, inner, aliases)
        return None, None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        inner = _unique_concrete_type(node, aliases)
        if not inner:
            return None, None
        return _type_ref_with_origin_for_name(node, inner, aliases)
    if isinstance(node, ast.Tuple):
        inner = _unique_concrete_type(node, aliases)
        if not inner:
            return None, None
        return _type_ref_with_origin_for_name(node, inner, aliases)
    return None, None


def _type_ref_with_origin_for_name(
    node: ast.AST | None,
    target: str,
    aliases: dict[str, str],
) -> tuple[str | None, str | None]:
    """Locate ``target`` inside ``node`` and return canonical name + origin."""
    found: list[tuple[str, str | None]] = []

    def walk(n: ast.AST | None) -> None:
        if n is None:
            return
        if isinstance(n, ast.Constant):
            # Skip None / Annotated metadata strings; quoted types are top-level only.
            return
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
            walk(n.left)
            walk(n.right)
            return
        if isinstance(n, ast.Tuple):
            for elt in n.elts:
                walk(elt)
            return
        if isinstance(n, ast.Name) and n.id == target:
            found.append(_canonicalize_type_via_imports(n.id, aliases))
            return
        if isinstance(n, ast.Attribute) and n.attr == target:
            found.append((n.attr, _module_path_for_attr_value(n.value, aliases)))
            return
        # Optional[Foo] / Union[...] / Annotated[Foo, ...] — descend into slice.
        if isinstance(n, ast.Subscript):
            walk(n.slice)

    walk(node)
    if not found:
        # Fall back to alias canonicalize of the simple name alone.
        return _canonicalize_type_via_imports(target, aliases)
    # All matches must agree on class + origin.
    uniq = list(dict.fromkeys(found))
    if len(uniq) == 1:
        return uniq[0]
    # Class name agrees but origins differ → keep name, drop origin.
    names = list(dict.fromkeys(c for c, _ in found))
    if len(names) == 1:
        return names[0], None
    return None, None


def _collect_return_factory_callees(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str] | None:
    """Callee tokens when every non-None return is a factory result.

    Accepts ``return inner(...)`` and ``return x`` after ``x = inner(...)``.
    CapWords constructors and unknown forms return ``None`` (not chainable here;
    constructors are handled by ``_infer_return_type``). Empty eligible set →
    ``None``. Used by map-level multi-hop chaining only.
    """
    factory_assigns = _collect_factory_assigns(func_node)
    found: list[str] = []

    class ReturnFactoryVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is func_node:
                self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is func_node:
                self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_Return(self, node: ast.Return) -> None:
            if node.value is None:
                return
            if isinstance(node.value, ast.Constant) and node.value.value is None:
                return
            factory = _factory_call_callee(node.value)
            if factory is not None:
                found.append(factory)
                return
            if isinstance(node.value, ast.Name) and node.value.id in factory_assigns:
                found.append(factory_assigns[node.value.id])
                return
            # Constructor / unknown / mixed — not a pure factory-return chain.
            found.append("")

    ReturnFactoryVisitor().visit(func_node)
    if not found or any(not t for t in found):
        return None
    return found


def _infer_return_type(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    import_aliases: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    """High-confidence ``(class_name, origin_mod|None)``, or ``(None, None)``.

    Prefer a unique return annotation. Else require every non-None ``return`` to
    agree on one concrete class from ``return Class(...)`` or ``return alias``
    where ``alias`` is uniquely bound in-scope. Import aliases canonicalize
    ``Foo as F`` / ``models.Foo`` and supply a dotted origin module for
    cross-file ``obj.method`` gating. Multi-class / unknown forms → None.

    Factory-only returns (``return inner()``) are left unset here; map-level
    ``_chain_factory_return_types`` may fill them when the callee's type is
    unique within the hop cap.
    """
    aliases = import_aliases or {}
    ann_name, ann_mod = _type_ref_with_origin(func_node.returns, aliases)
    if ann_name:
        return ann_name, ann_mod

    # CapWords ctors + local aliases only (factory chains resolved later).
    local, _local_mods = _collect_local_type_bindings(func_node, aliases)
    found: list[tuple[str | None, str | None]] = []

    class ReturnVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is func_node:
                self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is func_node:
                self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_Return(self, node: ast.Return) -> None:
            if node.value is None:
                return
            if isinstance(node.value, ast.Constant) and node.value.value is None:
                return
            if isinstance(node.value, ast.Call) and _constructor_type_name(node.value):
                found.append(_type_ref_with_origin(node.value, aliases))
                return
            if isinstance(node.value, ast.Name):
                bound = local.get(node.value.id)
                if bound:
                    found.append(_canonicalize_type_via_imports(bound, aliases))
                    return
                if _looks_like_class_name(node.value.id):
                    found.append(_canonicalize_type_via_imports(node.value.id, aliases))
                    return
            # Unknown / non-concrete return form — poison uniqueness.
            found.append((None, None))

    ReturnVisitor().visit(func_node)
    if any(t is None for t, _ in found):
        return None, None
    concrete = [(t, m) for t, m in found if t]
    names = list(dict.fromkeys(t for t, _ in concrete))
    if len(names) != 1:
        return None, None
    mods = list(dict.fromkeys(m for _, m in concrete if m))
    # Agree on class; keep origin only when unanimous (or single known).
    if len(mods) == 1:
        return names[0], mods[0]
    if len(mods) == 0:
        return names[0], None
    return names[0], None


def _collect_local_type_bindings(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    import_aliases: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Map local names → class names (+ optional origin mods) in scope.

    Only high-confidence bindings: annotated params/assigns and ``name = Class()``.
    Annotations go through ``_type_ref_with_origin`` so ``Foo as F``, quoted
    ``\"Foo\"``, ``Annotated`` / ``Final`` / ``Opt[Foo]`` canonicalize with import
    origin when known. Later rebinding to another concrete type overwrites;
    ambiguous/unknown clears. Factory calls (``name = make()``) are recorded
    separately for return-type propagation — they do not invent a class
    named ``make``.
    """
    aliases = import_aliases or {}
    types: dict[str, str] = {}
    mods: dict[str, str] = {}

    def _bind(name: str, class_name: str | None, origin: str | None) -> None:
        if class_name:
            types[name] = class_name
            if origin:
                mods[name] = origin
            else:
                mods.pop(name, None)
        else:
            types.pop(name, None)
            mods.pop(name, None)

    # Parameter annotations (skip self/cls without annotation).
    for arg in [
        *func_node.args.posonlyargs,
        *func_node.args.args,
        *func_node.args.kwonlyargs,
    ]:
        if arg.arg in {"self", "cls"}:
            continue
        t, mod = _type_ref_with_origin(arg.annotation, aliases)
        _bind(arg.arg, t, mod)

    class BindingVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            # Do not descend into nested defs — their bindings are their own.
            if node is func_node:
                self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is func_node:
                self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return  # nested class body is out of scope

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if isinstance(node.target, ast.Name):
                ann, ann_mod = _type_ref_with_origin(node.annotation, aliases)
                ctor = _constructor_type_name(node.value) if node.value is not None else None
                ctor_mod: str | None = None
                if ctor is not None and node.value is not None:
                    _, ctor_mod = _type_ref_with_origin(node.value, aliases)
                factory = _factory_call_callee(node.value) if node.value is not None else None
                if ctor:
                    _bind(node.target.id, ctor, ctor_mod)
                elif ann:
                    _bind(node.target.id, ann, ann_mod)
                elif factory is not None:
                    # Pending return-type bind — clear stale annotation confidence.
                    _bind(node.target.id, None, None)
                elif node.target.id in types:
                    # Explicit rebinding without a known type — drop confidence.
                    _bind(node.target.id, None, None)
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            ctor = _constructor_type_name(node.value)
            ctor_mod: str | None = None
            if ctor is not None:
                _, ctor_mod = _type_ref_with_origin(node.value, aliases)
            factory = _factory_call_callee(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if ctor:
                        _bind(target.id, ctor, ctor_mod)
                    elif factory is not None:
                        _bind(target.id, None, None)
                    elif target.id in types:
                        _bind(target.id, None, None)
            self.generic_visit(node)

    BindingVisitor().visit(func_node)
    return types, mods


def _collect_local_types(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    import_aliases: dict[str, str] | None = None,
) -> dict[str, str]:
    """Map local names → class names (thin wrapper over bindings collector)."""
    types, _mods = _collect_local_type_bindings(func_node, import_aliases)
    return types


def _collect_factory_assigns(
    func_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, str]:
    """Map local names → callee tokens for ``name = factory(...)`` assigns.

    Last assignment wins. CapWords constructors are excluded (handled as types).
    """
    assigns: dict[str, str] = {}

    class FactoryVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is func_node:
                self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is func_node:
                self.generic_visit(node)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            if isinstance(node.target, ast.Name):
                factory = _factory_call_callee(node.value) if node.value is not None else None
                if factory:
                    assigns[node.target.id] = factory
                else:
                    assigns.pop(node.target.id, None)
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            factory = _factory_call_callee(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if factory:
                        assigns[target.id] = factory
                    else:
                        assigns.pop(target.id, None)
            self.generic_visit(node)

    FactoryVisitor().visit(func_node)
    return assigns


def _local_func_name(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    class_stack: list[str],
    *,
    enclosing_func: str | None,
    func_depth: int,
) -> str:
    """Stable local name for map keys.

    * Class body methods: ``Class.method`` (nested classes: ``Outer.Inner.method``).
    * Nested functions (inside any def): ``Enclosing.nested`` so they do not collide
      with sibling methods or other nested defs.
    * Top-level functions: bare ``def`` name (backward-compatible ``file:func``).
    """
    if enclosing_func is not None and func_depth > 0:
        return f"{enclosing_func}.{node.name}"
    if class_stack and func_depth == 0:
        return ".".join([*class_stack, node.name])
    return node.name


def _parse_file(file_path: pathlib.Path) -> dict[str, Any]:
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    calls_by_func: dict[str, list[str]] = {}
    complexity_by_func: dict[str, int] = {}
    side_effects_by_func: dict[str, list[str]] = {}
    hint_flags_by_func: dict[str, dict[str, Any]] = {}
    import_aliases = _collect_import_aliases(tree, file_path)
    current_func: str | None = None
    class_stack: list[str] = []
    func_depth = 0

    class Visitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            class_stack.append(node.name)
            self.generic_visit(node)
            class_stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef):
            nonlocal current_func, func_depth
            prev = current_func
            current_func = _local_func_name(
                node,
                class_stack,
                enclosing_func=prev,
                func_depth=func_depth,
            )
            calls_by_func[current_func] = []
            complexity_by_func[current_func] = _cyclomatic_complexity(node)
            side_effects_by_func[current_func] = _side_effects_for_func(node)
            hint_flags_by_func[current_func] = _func_type_hint_flags(node)
            func_depth += 1
            self.generic_visit(node)
            func_depth -= 1
            current_func = prev

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            # Treat async defs like sync defs for call-graph mapping + complexity.
            self.visit_FunctionDef(node)  # type: ignore[arg-type]

        def visit_Call(self, node: ast.Call):
            if current_func is not None:
                callee = None
                if isinstance(node.func, ast.Name):
                    callee = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    # Name-rooted chains: mod.fn or pkg.mod.fn (resolved later).
                    callee = _attr_call_token(node.func)
                if callee:
                    calls_by_func[current_func].append(callee)
            self.generic_visit(node)

    Visitor().visit(tree)

    # Second pass: local type bindings + enclosing class per function/method.
    enclosing_by_func: dict[str, str | None] = {}
    local_types_by_func: dict[str, dict[str, str]] = {}
    local_type_mods_by_func: dict[str, dict[str, str]] = {}
    factory_assigns_by_func: dict[str, dict[str, str]] = {}
    return_type_by_func: dict[str, str | None] = {}
    return_type_mod_by_func: dict[str, str | None] = {}
    return_factory_callees_by_func: dict[str, list[str]] = {}
    class_stack2: list[str] = []
    func_depth2 = 0
    current_func2: str | None = None

    class MetaVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            class_stack2.append(node.name)
            self.generic_visit(node)
            class_stack2.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            nonlocal current_func2, func_depth2
            prev = current_func2
            local = _local_func_name(
                node,
                class_stack2,
                enclosing_func=prev,
                func_depth=func_depth2,
            )
            enclosing_by_func[local] = (
                ".".join(class_stack2) if class_stack2 and func_depth2 == 0 else None
            )
            types, mods = _collect_local_type_bindings(node, import_aliases)
            local_types_by_func[local] = types
            local_type_mods_by_func[local] = mods
            factory_assigns_by_func[local] = _collect_factory_assigns(node)
            ret_name, ret_mod = _infer_return_type(node, import_aliases)
            return_type_by_func[local] = ret_name
            return_type_mod_by_func[local] = ret_mod
            # Only record chain candidates when local inference did not settle.
            if not ret_name:
                callees = _collect_return_factory_callees(node)
                if callees:
                    return_factory_callees_by_func[local] = callees
            current_func2 = local
            func_depth2 += 1
            self.generic_visit(node)
            func_depth2 -= 1
            current_func2 = prev

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.visit_FunctionDef(node)  # type: ignore[arg-type]

    MetaVisitor().visit(tree)

    out = {}
    for func, calls in calls_by_func.items():
        flags = hint_flags_by_func.get(func, {})
        simple = func.rsplit(".", 1)[-1]
        ret = return_type_by_func.get(func)
        ret_mod = return_type_mod_by_func.get(func)
        meta: dict[str, Any] = {
            "file": str(file_path.as_posix()),
            "calls": calls,
            "callers": [],
            "complexity": complexity_by_func.get(func, 1),
            "side_effects": side_effects_by_func.get(func, []),
            "has_docstring": bool(flags.get("has_docstring", False)),
            "has_return_annotation": bool(flags.get("has_return_annotation", False)),
            "has_type_hints": bool(flags.get("has_type_hints", False)),
            "typed_params": int(flags.get("typed_params", 0)),
            "total_params": int(flags.get("total_params", 0)),
            "fully_typed_params": bool(flags.get("fully_typed_params", False)),
            # Bare def/method name for consumers that still key on short names.
            "simple_name": simple,
            "analyzer": "python-ast",
            "complexity_kind": "mccabe",
            "language": "python",
            # Local import map for cross-file resolution at map-build time.
            "_import_aliases": import_aliases,
            # Class body for methods (None for top-level / nested defs).
            "_enclosing_class": enclosing_by_func.get(func),
            # High-confidence local name → class bindings (annotations / ctors).
            "_local_types": local_types_by_func.get(func) or {},
            # Module path gate for imported / return-propagated bindings.
            "_local_type_mods": local_type_mods_by_func.get(func) or {},
            # ``name = factory()`` pending binds for inter-procedural return types.
            "_factory_assigns": factory_assigns_by_func.get(func) or {},
        }
        chain = return_factory_callees_by_func.get(func)
        if chain:
            meta["_return_factory_callees"] = chain
        if ret:
            meta["return_type"] = ret
            meta["_return_type"] = ret
            if ret_mod:
                meta["_return_type_mod"] = ret_mod
        out[func] = meta
    return out


def _match_module_path(file_path: str, mod_path: str) -> bool:
    """True when ``file_path`` is the module file for dotted ``mod_path``.

    Matches ``pkg/mod.py`` for ``pkg.mod`` and ``pkg/__init__.py`` for ``pkg``.
    """
    posix = file_path.replace("\\", "/")
    mod_suffix = mod_path.replace(".", "/")
    if not mod_suffix:
        return False
    if posix.endswith(mod_suffix + ".py"):
        return True
    if posix.endswith(mod_suffix + "/__init__.py"):
        return True
    return False


def _resolve_via_module_path(
    mod_path: str,
    func_name: str,
    by_short: dict[str, list[str]],
    functions: dict[str, Any],
) -> list[str]:
    """Unique match of ``func_name`` under ``mod_path``, or empty if ambiguous/missing."""
    candidates = list(dict.fromkeys(by_short.get(func_name, [])))
    if not candidates:
        return []
    matched = [
        qn for qn in candidates if _match_module_path(functions[qn].get("file", ""), mod_path)
    ]
    # Prefer exact local-name match (``Class.method`` vs basename ``method``).
    exact = [qn for qn in matched if qn.rsplit(":", 1)[-1] == func_name]
    if len(exact) == 1:
        return exact
    if len(matched) == 1:
        return matched
    return []


def _build_call_indexes(
    functions: dict[str, Any],
) -> tuple[dict[str, list[str]], dict[str, dict[str, list[str]]]]:
    """Build short-name and per-file short-name indexes in one O(n) pass.

    Keys after ``:`` may be ``func`` or ``Class.method``. Both the full local
    name and the trailing method segment are indexed so ``self.method`` can
    resolve to ``Class.method`` when unique. Duplicate basenames stay listed
    (callers must apply uniqueness gates — never invent edges).

    ``by_file_short[file][short]`` avoids repeated full-map file filters during
    attach/qualify (was O(candidates) scans per call site).
    """
    by_short: dict[str, list[str]] = {}
    by_file_short: dict[str, dict[str, list[str]]] = {}
    for qn, meta in functions.items():
        short = qn.rsplit(":", 1)[-1]
        file = meta.get("file", "")
        by_short.setdefault(short, []).append(qn)
        fmap = by_file_short.setdefault(file, {})
        fmap.setdefault(short, []).append(qn)
        if "." in short:
            base = short.rsplit(".", 1)[-1]
            by_short.setdefault(base, []).append(qn)
            fmap.setdefault(base, []).append(qn)
    return by_short, by_file_short


def _index_by_short(functions: dict[str, Any]) -> dict[str, list[str]]:
    """Index qnames by local name and method basename (thin wrapper)."""
    by_short, _ = _build_call_indexes(functions)
    return by_short


def _file_short_unique(
    by_file_short: dict[str, dict[str, list[str]]],
    caller_file: str,
    key: str,
) -> list[str]:
    """Unique same-file qnames for ``key``, else []."""
    local = list(dict.fromkeys(by_file_short.get(caller_file, {}).get(key, [])))
    if len(local) == 1:
        return local
    return []


def _resolve_typed_attr(
    class_name: str,
    attr: str,
    by_short: dict[str, list[str]],
    functions: dict[str, Any],
    caller_file: str,
    by_file_short: dict[str, dict[str, list[str]]] | None = None,
) -> list[str]:
    """Resolve ``Class.attr`` when type is known — uniqueness-gated, no fan-out.

    Prefers same-file exact local name ``Class.attr``. Falls back to a single
    global exact match. Never returns multiple candidates.
    """
    local_key = f"{class_name}.{attr}"
    if by_file_short is not None:
        same_file = _file_short_unique(by_file_short, caller_file, local_key)
        if same_file:
            return same_file
    candidates = list(dict.fromkeys(by_short.get(local_key, [])))
    # Also accept basename index entries that are exactly Class.attr
    for qn in by_short.get(attr, []):
        if qn.rsplit(":", 1)[-1] == local_key and qn not in candidates:
            candidates.append(qn)
    exact = [qn for qn in candidates if qn.rsplit(":", 1)[-1] == local_key]
    if by_file_short is None:
        same_file = [qn for qn in exact if functions[qn].get("file") == caller_file]
        if len(same_file) == 1:
            return same_file
    if len(exact) == 1:
        return exact
    return []


def _resolve_imported_class_attr(
    mod_path: str,
    class_name: str,
    attr: str,
    by_short: dict[str, list[str]],
    functions: dict[str, Any],
) -> list[str]:
    """Resolve ``Class.attr`` under imported module ``mod_path`` when unique.

    Used for ``from mod import Foo`` then ``Foo.method`` / typed ``obj.method``
    where ``obj`` is annotated or constructed as ``Foo``. Ambiguous or missing
    matches return [] — never invent edges.
    """
    local_key = f"{class_name}.{attr}"
    candidates = [
        qn
        for qn in dict.fromkeys(by_short.get(local_key, []))
        if qn.rsplit(":", 1)[-1] == local_key
        and _match_module_path(functions[qn].get("file", ""), mod_path)
    ]
    if len(candidates) == 1:
        return candidates
    return []


def _resolve_class_attr_via_aliases(
    class_name: str,
    attr: str,
    aliases: dict[str, str],
    by_short: dict[str, list[str]],
    functions: dict[str, Any],
    caller_file: str,
    *,
    origin_mod: str | None = None,
) -> list[str]:
    """Typed / imported-class resolve with import-alias gating when available.

    If ``class_name`` maps to ``from mod import Class`` / ``as`` alias
    (``mod:Class``), prefer the module-gated ``Class.attr`` match — this
    uniquifies cross-file even when another scanned file defines a same-named
    class. When the import is present but no unique method exists, omit (do not
    fall back to a different file's class).

    ``origin_mod`` may be:
      * a defining **file path** (return-type propagation from a factory file), or
      * a dotted **module path** (imported return type / ``models.Foo`` annotation).

    File origins prefer ``Class.attr`` in that file, then the file's module path,
    then unique global. Module origins are import-gated only — no ambiguous
    global fallthrough.
    """
    binding = aliases.get(class_name)
    if binding is not None and ":" in binding:
        base, imported = binding.rsplit(":", 1)
        via = _resolve_imported_class_attr(base, imported, attr, by_short, functions)
        if via:
            return via
        # Import known but no unique Class.attr under that module — omit.
        return []
    if origin_mod:
        # Dotted module path (no path separators / .py suffix).
        is_file = origin_mod.endswith(".py") or "/" in origin_mod or "\\" in origin_mod
        if not is_file:
            via_mod = _resolve_imported_class_attr(
                origin_mod, class_name, attr, by_short, functions
            )
            if via_mod:
                return via_mod
            # Known imported-return origin but no unique match — refuse.
            return []
        # origin_mod holds the factory's file path (not a dotted module).
        via_file = _resolve_class_attr_in_file(class_name, attr, origin_mod, by_short, functions)
        if via_file:
            return via_file
        mod = _module_path_from_file(origin_mod)
        if mod:
            via_mod = _resolve_imported_class_attr(mod, class_name, attr, by_short, functions)
            if via_mod:
                return via_mod
        return _resolve_typed_attr(class_name, attr, by_short, functions, caller_file)
    return _resolve_typed_attr(class_name, attr, by_short, functions, caller_file)


def _resolve_attr_call(
    dotted: str,
    aliases: dict[str, str],
    by_short: dict[str, list[str]],
    functions: dict[str, Any],
    caller_file: str,
    *,
    enclosing_class: str | None = None,
    local_types: dict[str, str] | None = None,
    local_type_mods: dict[str, str] | None = None,
    by_file_short: dict[str, dict[str, list[str]]] | None = None,
) -> list[str]:
    """Resolve ``mod.fn`` / ``self.method`` / typed ``obj.method`` / ``pkg.mod.fn``.

    Policy:
      * ``root.attr`` (one dot):
          - ``import`` alias (no ``:``): unique module-path resolve.
          - ``from pkg import mod`` (``pkg:mod``): if ``pkg.mod`` uniquely hosts
            ``attr``, use it (module-from-import).
          - ``from mod import Foo`` (class): ``Foo.method`` via module-gated
            ``Class.method`` when unique.
          - ``self`` with known enclosing class: ``Class.attr`` uniqueness gate.
          - Root with high-confidence local type (annotation/ctor/return-prop):
            typed resolve (import-alias or factory-module gated when known).
          - Untyped ``obj.method`` / unbound ``self``: **refuse** (do not guess
            via same-file unique basename — that invented edges).
      * ``pkg.mod.fn`` (two dots), high confidence only:
          - ``pkg`` is an ``import`` alias → resolve ``pkg.mod`` + ``fn``.
          - Else omit (do not invent nested edges).
      * Longer chains: omit.
      * Never fan out to all global short-name matches for attribute forms.
    """
    parts = dotted.split(".")
    if len(parts) == 2:
        root, attr = parts
        binding = aliases.get(root)
        if binding is not None and ":" not in binding:
            return _resolve_via_module_path(binding, attr, by_short, functions)
        if binding is not None and ":" in binding:
            # from pkg import mod  → binding "pkg:mod"; try submodule pkg.mod.
            base, imported = binding.rsplit(":", 1)
            submodule = f"{base}.{imported}" if base else imported
            via_mod = _resolve_via_module_path(submodule, attr, by_short, functions)
            if via_mod:
                return via_mod
            # from mod import Foo → Foo.method (imported class, not a submodule).
            via_cls = _resolve_imported_class_attr(base, imported, attr, by_short, functions)
            if via_cls:
                return via_cls
            # Imported symbol is neither a module nor a scanned class method.
            return []
        if root == "self":
            # Honesty: only Class.method when enclosing class is known.
            if not enclosing_class:
                return []
            return _resolve_typed_attr(
                enclosing_class,
                attr,
                by_short,
                functions,
                caller_file,
                by_file_short=by_file_short,
            )
        local_types = local_types or {}
        local_type_mods = local_type_mods or {}
        if root in local_types:
            typed = _resolve_class_attr_via_aliases(
                local_types[root],
                attr,
                aliases,
                by_short,
                functions,
                caller_file,
                origin_mod=local_type_mods.get(root),
            )
            if typed:
                return typed
            return []
        # Untyped obj.method — refuse rather than same-file basename guess.
        return []
    if len(parts) == 3:
        root, mid, attr = parts
        binding = aliases.get(root)
        if binding is not None and ":" not in binding:
            return _resolve_via_module_path(f"{binding}.{mid}", attr, by_short, functions)
        return []
    return []


def _resolve_bare_or_dotted_callee(
    callee_token: str,
    aliases: dict[str, str],
    by_short: dict[str, list[str]],
    functions: dict[str, Any],
    caller_file: str,
    caller_qn: str,
    by_file_short: dict[str, dict[str, list[str]]] | None = None,
) -> list[str]:
    """Unique callee qname for a bare or dotted call token (same policy as callers)."""
    if "." in callee_token:
        return _resolve_attr_call(
            callee_token,
            aliases,
            by_short,
            functions,
            caller_file,
            by_file_short=by_file_short,
        )
    if by_file_short is not None:
        same_file = list(dict.fromkeys(by_file_short.get(caller_file, {}).get(callee_token, [])))
    else:
        candidates = list(dict.fromkeys(by_short.get(callee_token, [])))
        same_file = [c for c in candidates if functions[c].get("file") == caller_file]
    if same_file:
        caller_local = caller_qn.rsplit(":", 1)[-1]
        nested = [c for c in same_file if c.rsplit(":", 1)[-1] == f"{caller_local}.{callee_token}"]
        if len(nested) == 1:
            return nested
        exact = [c for c in same_file if c.rsplit(":", 1)[-1] == callee_token]
        if len(exact) == 1:
            return exact
        if exact:
            return []
        return same_file if len(same_file) == 1 else []
    candidates = list(dict.fromkeys(by_short.get(callee_token, [])))
    if not candidates:
        return []
    imported = _resolve_via_import(callee_token, aliases, by_short, functions)
    if imported:
        return imported
    if len(candidates) == 1:
        return candidates
    return []


def _propagate_return_types(
    functions: dict[str, Any],
    *,
    by_short: dict[str, list[str]] | None = None,
    by_file_short: dict[str, dict[str, list[str]]] | None = None,
) -> None:
    """Bind ``obj = factory()`` locals from high-confidence callee return types.

    Only when the factory uniquely resolves and exposes a single concrete
    ``_return_type``. Origin gating for later ``obj.method`` resolve prefers
    ``_return_type_mod`` (imported / ``models.Foo``) when present; otherwise
    the factory's defining file. Ambiguous factories / multi-return types
    leave the bind unset.
    """
    if by_short is None or by_file_short is None:
        by_short, by_file_short = _build_call_indexes(functions)
    for caller_qn, meta in functions.items():
        factories: dict[str, str] = meta.get("_factory_assigns") or {}
        if not factories:
            continue
        aliases: dict[str, str] = meta.get("_import_aliases") or {}
        caller_file = meta.get("file", "")
        local_types: dict[str, str] = meta.setdefault("_local_types", {})
        local_mods: dict[str, str] = meta.setdefault("_local_type_mods", {})
        for local_name, callee_token in factories.items():
            if local_name in local_types:
                # Annotation / ctor already won — do not overwrite.
                continue
            chosen = _resolve_bare_or_dotted_callee(
                callee_token,
                aliases,
                by_short,
                functions,
                caller_file,
                caller_qn,
                by_file_short=by_file_short,
            )
            if len(chosen) != 1:
                continue
            callee_meta = functions[chosen[0]]
            ret = callee_meta.get("_return_type") or callee_meta.get("return_type")
            if not ret or not isinstance(ret, str):
                continue
            local_types[local_name] = ret
            ret_mod = callee_meta.get("_return_type_mod")
            if isinstance(ret_mod, str) and ret_mod:
                # Dotted module from imported return type — import-gated resolve.
                local_mods[local_name] = ret_mod
            else:
                # Store defining file for Class.attr gating (absolute paths are OK).
                local_mods[local_name] = callee_meta.get("file", "")


_MAX_RETURN_TYPE_HOPS = 3


def _chain_factory_return_types(
    functions: dict[str, Any],
    *,
    max_hops: int = _MAX_RETURN_TYPE_HOPS,
    by_short: dict[str, list[str]] | None = None,
    by_file_short: dict[str, dict[str, list[str]]] | None = None,
) -> None:
    """Propagate return types through ``return inner()`` factory chains.

    Only when every non-None return is a uniquely resolvable factory whose
    concrete ``_return_type`` agrees. Cap at ``max_hops`` rounds so
    ``outer → mid → inner → Foo`` (3 hops) can settle; longer / cyclic /
    ambiguous chains stay unset. Runs before ``_propagate_return_types``.
    """
    if by_short is None or by_file_short is None:
        by_short, by_file_short = _build_call_indexes(functions)
    for _ in range(max(0, max_hops)):
        progressed = False
        for caller_qn, meta in functions.items():
            if meta.get("_return_type") or meta.get("return_type"):
                continue
            tokens: list[str] = meta.get("_return_factory_callees") or []
            if not tokens:
                continue
            aliases: dict[str, str] = meta.get("_import_aliases") or {}
            caller_file = meta.get("file", "")
            resolved: list[tuple[str, str | None]] = []
            incomplete = False
            refuse = False
            for tok in tokens:
                chosen = _resolve_bare_or_dotted_callee(
                    tok,
                    aliases,
                    by_short,
                    functions,
                    caller_file,
                    caller_qn,
                    by_file_short=by_file_short,
                )
                if len(chosen) != 1:
                    refuse = True
                    break
                cal_qn = chosen[0]
                if cal_qn == caller_qn:
                    refuse = True
                    break
                cal_meta = functions[cal_qn]
                ret = cal_meta.get("_return_type") or cal_meta.get("return_type")
                if not ret or not isinstance(ret, str):
                    incomplete = True
                    break
                ret_mod = cal_meta.get("_return_type_mod")
                if isinstance(ret_mod, str) and ret_mod:
                    origin: str | None = ret_mod
                else:
                    # Prefer callee file so later obj.method gating stays local.
                    origin = cal_meta.get("file") or None
                resolved.append((ret, origin))
            if refuse or incomplete or not resolved:
                if refuse:
                    # Ambiguous / self-cycle — drop chain candidate permanently.
                    meta.pop("_return_factory_callees", None)
                continue
            names = list(dict.fromkeys(r for r, _ in resolved))
            if len(names) != 1:
                meta.pop("_return_factory_callees", None)
                continue
            mods = list(dict.fromkeys(m for _, m in resolved if m))
            meta["_return_type"] = names[0]
            meta["return_type"] = names[0]
            if len(mods) == 1:
                meta["_return_type_mod"] = mods[0]
            else:
                meta.pop("_return_type_mod", None)
            meta.pop("_return_factory_callees", None)
            progressed = True
        if not progressed:
            break


def _attach_callers(
    functions: dict[str, Any],
    *,
    by_short: dict[str, list[str]] | None = None,
    by_file_short: dict[str, dict[str, list[str]]] | None = None,
) -> None:
    """Populate reverse call edges (callers) from ``calls`` lists.

    Resolution policy (reduces cross-file false positives):
      1. Dotted forms: high-confidence module / module-from-import / typed /
         enclosing-class ``self`` — never untyped same-file basename guess.
      2. Bare names: prefer same-file callees when any exist.
      3. Else, if import alias maps the name to ``module:func`` and exactly one
         global qn matches that module path + func (high confidence), use it.
      4. Else, if exactly one global candidate shares the short name, use it.
      5. Else (ambiguous cross-file), skip the edge — do not fan out to all.
    """
    if by_short is None or by_file_short is None:
        by_short, by_file_short = _build_call_indexes(functions)

    for meta in functions.values():
        meta.setdefault("callers", [])

    for caller_qn, meta in functions.items():
        caller_file = meta.get("file", "")
        aliases: dict[str, str] = meta.get("_import_aliases") or {}
        enclosing = meta.get("_enclosing_class")
        local_types: dict[str, str] = meta.get("_local_types") or {}
        local_type_mods: dict[str, str] = meta.get("_local_type_mods") or {}
        for callee_token in meta.get("calls", []):
            if "." in callee_token:
                chosen = _resolve_attr_call(
                    callee_token,
                    aliases,
                    by_short,
                    functions,
                    caller_file,
                    enclosing_class=enclosing,
                    local_types=local_types,
                    local_type_mods=local_type_mods,
                    by_file_short=by_file_short,
                )
                if not chosen:
                    continue
            else:
                candidates = list(dict.fromkeys(by_short.get(callee_token, [])))
                if not candidates:
                    continue
                same_file = list(
                    dict.fromkeys(by_file_short.get(caller_file, {}).get(callee_token, []))
                )
                if same_file:
                    caller_local = caller_qn.rsplit(":", 1)[-1]
                    # Nested def under this caller: Foo.run -> helper => Foo.run.helper
                    nested = [
                        c
                        for c in same_file
                        if c.rsplit(":", 1)[-1] == f"{caller_local}.{callee_token}"
                    ]
                    if len(nested) == 1:
                        chosen = nested
                    else:
                        # Prefer exact local-name key match when basename indexing
                        # pulled in Class.method alongside a top-level def.
                        exact = [c for c in same_file if c.rsplit(":", 1)[-1] == callee_token]
                        if exact:
                            chosen = exact
                        elif len(same_file) == 1:
                            chosen = same_file
                        else:
                            # Ambiguous Class.method basenames — omit.
                            continue
                else:
                    chosen = _resolve_via_import(callee_token, aliases, by_short, functions)
                    if not chosen:
                        if len(candidates) == 1:
                            chosen = candidates
                        else:
                            # Ambiguous across files — omit rather than invent edges.
                            continue
            for callee_qn in chosen:
                if callee_qn != caller_qn:
                    functions[callee_qn]["callers"].append(caller_qn)

    for meta in functions.values():
        meta["callers"] = sorted(set(meta["callers"]))


def _resolve_via_import(
    callee_short: str,
    aliases: dict[str, str],
    by_short: dict[str, list[str]],
    functions: dict[str, Any],
) -> list[str]:
    """High-confidence cross-file resolve using ``from mod import name`` aliases."""
    target = aliases.get(callee_short)
    if not target or ":" not in target:
        return []
    mod_path, func_name = target.rsplit(":", 1)
    return _resolve_via_module_path(mod_path, func_name, by_short, functions)


def _qualify_calls(
    functions: dict[str, Any],
    *,
    by_short: dict[str, list[str]] | None = None,
    by_file_short: dict[str, dict[str, list[str]]] | None = None,
) -> None:
    """Rewrite ``calls`` to file-local qualified names when unambiguous.

    Same-file unique callees become ``rel/path:func`` (or ``rel/path:Class.method``).
    Unresolved / ambiguous names stay as bare or dotted tokens. Import-resolved
    cross-file edges also get the matched qn when unique. Strips internal
    ``_import_aliases``, ``_enclosing_class``, ``_local_types``, ``_local_type_mods``,
    ``_factory_assigns``, ``_return_factory_callees``, ``_return_type``,
    ``_return_type_mod``.
    """
    if by_short is None or by_file_short is None:
        by_short, by_file_short = _build_call_indexes(functions)

    for _caller_qn, meta in functions.items():
        aliases: dict[str, str] = meta.pop("_import_aliases", None) or {}
        enclosing = meta.pop("_enclosing_class", None)
        local_types: dict[str, str] = meta.pop("_local_types", None) or {}
        local_type_mods: dict[str, str] = meta.pop("_local_type_mods", None) or {}
        meta.pop("_factory_assigns", None)
        meta.pop("_return_factory_callees", None)
        meta.pop("_return_type", None)
        meta.pop("_return_type_mod", None)
        caller_file = meta.get("file", "")
        qualified: list[str] = []
        for callee_token in meta.get("calls", []):
            if "." in callee_token:
                resolved = _resolve_attr_call(
                    callee_token,
                    aliases,
                    by_short,
                    functions,
                    caller_file,
                    enclosing_class=enclosing,
                    local_types=local_types,
                    local_type_mods=local_type_mods,
                    by_file_short=by_file_short,
                )
                if len(resolved) == 1:
                    qualified.append(resolved[0])
                else:
                    qualified.append(callee_token)
                continue
            local_map = by_file_short.get(caller_file, {})
            local = list(dict.fromkeys(local_map.get(callee_token, [])))
            caller_local = _caller_qn.rsplit(":", 1)[-1]
            nested = [c for c in local if c.rsplit(":", 1)[-1] == f"{caller_local}.{callee_token}"]
            exact = [c for c in local if c.rsplit(":", 1)[-1] == callee_token]
            if len(nested) == 1:
                pick = nested
            elif len(exact) == 1:
                pick = exact
            elif len(local) == 1:
                pick = local
            else:
                pick = []
            if len(pick) == 1:
                qualified.append(pick[0])
                continue
            imported = _resolve_via_import(callee_token, aliases, by_short, functions)
            if len(imported) == 1:
                qualified.append(imported[0])
                continue
            qualified.append(callee_token)
        meta["calls"] = qualified


def _open_cache(cache_path: pathlib.Path):
    conn = sqlite3.connect(str(cache_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, mtime INTEGER, size INTEGER, sha TEXT, data TEXT)"
    )
    return conn


def build_python_map(
    root: pathlib.Path,
    use_cache: bool = False,
    processes: int | None = None,
    cache_path: pathlib.Path | None = None,
) -> dict[str, Any]:
    functions: dict[str, Any] = {}
    files: list[pathlib.Path] = []
    for p, _, files_in_dir in os.walk(root):
        for name in files_in_dir:
            path = pathlib.Path(p) / name
            if _is_code_file(path):
                files.append(path)

    def qn(file_path: pathlib.Path, func_name: str) -> str:
        rel = file_path.with_suffix("").as_posix()
        return f"{rel}:{func_name}"

    cache_conn = None
    cache = {}
    if use_cache:
        cp = cache_path or (root / "maps" / "cache.sqlite")
        cp.parent.mkdir(parents=True, exist_ok=True)
        cache_conn = _open_cache(cp)
        for path, mtime, size, sha, data in cache_conn.execute(
            "SELECT path, mtime, size, sha, data FROM files"
        ):
            cache[path] = (mtime, size, sha, data)

    work: list[pathlib.Path] = []
    for file_path in files:
        if cache_conn is not None:
            mtime, size, sha = _file_signature(file_path)
            row = cache.get(str(file_path.as_posix()))
            if row and row[0] == mtime and row[1] == size and row[2] == sha:
                # reuse cached
                data = json.loads(row[3])
                for func, meta in data.items():
                    functions[qn(file_path, func)] = meta
                continue
        work.append(file_path)

    time.time()
    results = []
    if work:
        procs = max(1, processes or min(4, cpu_count()))
        if procs > 1:
            with Pool(processes=procs) as pool:
                results = pool.map(_parse_file, work)
        else:
            results = [_parse_file(fp) for fp in work]
        # write results and update cache
        for file_path, data in zip(work, results):
            for func, meta in data.items():
                functions[qn(file_path, func)] = meta
            if cache_conn is not None:
                mtime, size, sha = _file_signature(file_path)
                import json as _json

                cache_conn.execute(
                    "REPLACE INTO files(path, mtime, size, sha, data) VALUES (?,?,?,?,?)",
                    (str(file_path.as_posix()), mtime, size, sha, _json.dumps(data)),
                )
        if cache_conn is not None:
            cache_conn.commit()

    by_short, by_file_short = _build_call_indexes(functions)
    _chain_factory_return_types(functions, by_short=by_short, by_file_short=by_file_short)
    _propagate_return_types(functions, by_short=by_short, by_file_short=by_file_short)
    _attach_callers(functions, by_short=by_short, by_file_short=by_file_short)
    _qualify_calls(functions, by_short=by_short, by_file_short=by_file_short)
    return {
        "language": "python",
        "functions": functions,
        "analyzer": "python-ast",
        "analyzer_fidelity": "ast",
        "complexity_kind": "mccabe",
        "analyzer_note": (
            "Python AST map with McCabe complexity; call edges are high-confidence "
            "only (ambiguous names omit rather than invent)."
        ),
    }
