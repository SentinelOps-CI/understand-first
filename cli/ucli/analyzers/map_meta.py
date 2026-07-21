"""Shared map/lens metadata helpers for multi-language honesty (Wave 16)."""

from __future__ import annotations

from typing import Any


def map_fidelity_label(repo_map: dict[str, Any]) -> str:
    """Return a short fidelity label for a map or lens carrying map metadata."""
    fidelity = repo_map.get("analyzer_fidelity")
    if isinstance(fidelity, dict):
        if not fidelity:
            return "unknown"
        vals = set(str(v) for v in fidelity.values())
        if vals == {"ast"}:
            return "ast"
        if "best-effort" in vals and "ast" in vals:
            return "mixed"
        if vals == {"best-effort"}:
            return "best-effort"
        return ",".join(sorted(vals))
    if isinstance(fidelity, str) and fidelity:
        return fidelity
    # Flat analyzer id on single-language maps
    analyzer = str(repo_map.get("analyzer") or "")
    if analyzer.endswith("-ast"):
        return "ast"
    if "best-effort" in analyzer:
        return "best-effort"
    # Infer from function analyzer tags
    kinds = {
        str(m.get("analyzer", ""))
        for m in (repo_map.get("functions") or {}).values()
        if isinstance(m, dict)
    }
    kinds.discard("")
    if kinds and all(k.endswith("-ast") for k in kinds):
        return "ast"
    if kinds == {"python-ast"} or (kinds and all(k.startswith("python") for k in kinds)):
        return "ast"
    if kinds and all("best-effort" in k for k in kinds):
        return "best-effort"
    if kinds:
        return "mixed"
    lang = repo_map.get("language")
    if lang in {"python"}:
        return "ast"
    if lang in {"javascript", "typescript", "go", "java", "rust", "csharp"}:
        # Unknown path — do not claim AST.
        return "best-effort"
    if lang == "mixed":
        return "mixed"
    return "unknown"


def complexity_semantics_note(repo_map: dict[str, Any]) -> str:
    label = map_fidelity_label(repo_map)
    kind = repo_map.get("complexity_kind")
    analyzer = str(repo_map.get("analyzer") or "")
    if kind == "ast-cyclomatic" or (
        label == "ast" and analyzer.endswith("-ast") and analyzer != "python-ast"
    ):
        return (
            "Complexity values are ast-cyclomatic on JS/TS/Go/Java/Rust/C# AST "
            "(decision points; see analyzer_note for formula) — not Python McCabe."
        )
    if label == "ast":
        return "Complexity values are McCabe cyclomatic (Python AST)."
    if label == "best-effort":
        return (
            "Complexity values are keyword-heuristic "
            "(JS/TS/Go/Java/Rust/C# best-effort) — not McCabe AST."
        )
    if label == "mixed":
        return (
            "Complexity mixes McCabe / ast-cyclomatic (AST languages) and "
            "keyword-heuristic (regex fallback); do not treat totals as uniform McCabe."
        )
    return "Complexity semantics depend on the producing analyzer; check analyzer_fidelity."


def annotate_lens_from_map(lens: dict[str, Any], repo_map: dict[str, Any]) -> dict[str, Any]:
    """Copy map language/fidelity metadata onto a lens for downstream honesty."""
    lens_meta = lens.setdefault("lens", {})
    for key in (
        "language",
        "languages_analyzed",
        "analyzer_fidelity",
        "analyzer_notes",
        "unsupported",
    ):
        if key in repo_map and key not in lens_meta:
            lens_meta[key] = repo_map[key]
    # Flat copies some consumers already look for on the document root.
    if "language" in repo_map:
        lens.setdefault("language", repo_map["language"])
    if "analyzer_fidelity" in repo_map:
        lens.setdefault("analyzer_fidelity", repo_map["analyzer_fidelity"])
    lens_meta["complexity_note"] = complexity_semantics_note(repo_map)
    lens_meta["fidelity"] = map_fidelity_label(repo_map)
    return lens


def lens_has_python_files(lens: dict[str, Any]) -> bool:
    for meta in (lens.get("functions") or {}).values():
        if isinstance(meta, dict) and str(meta.get("file", "")).endswith(".py"):
            return True
    return False


def lens_runtime_trace_supported(lens: dict[str, Any]) -> bool:
    """Runtime ``u trace`` / ``tour_run`` fixtures are Python-only today."""
    return lens_has_python_files(lens)
