"""Language analyzers and multi-language scan dispatch."""

from __future__ import annotations

from ucli.analyzers.csharp_analyzer import build_csharp_map
from ucli.analyzers.go_analyzer import build_go_map
from ucli.analyzers.java_analyzer import build_java_map
from ucli.analyzers.js_analyzer import build_js_map
from ucli.analyzers.python_analyzer import build_python_map
from ucli.analyzers.registry import (
    build_repo_map,
    format_unsupported_summary,
    registered_adapters,
    supported_extensions,
    supported_languages,
)
from ucli.analyzers.rust_analyzer import build_rust_map

__all__ = [
    "build_csharp_map",
    "build_go_map",
    "build_java_map",
    "build_js_map",
    "build_python_map",
    "build_rust_map",
    "build_repo_map",
    "format_unsupported_summary",
    "registered_adapters",
    "supported_extensions",
    "supported_languages",
]
