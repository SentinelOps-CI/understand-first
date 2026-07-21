import os
import re


def _read(path):
    return open(path, encoding="utf-8", errors="ignore").read()


def build_glossary(root: str = ".") -> str:
    terms: list[str] = []
    # OpenAPI paths and schema names
    for r, _d, files in os.walk(root):
        for f in files:
            if (
                f.endswith((".yml", ".yaml"))
                and "openapi" in _read(os.path.join(r, f))[:200].lower()
            ):
                data = _read(os.path.join(r, f))
                terms += re.findall(r"\n\s{0,6}(/[^\s:]+):", data)
                terms += re.findall(r"\bcomponents:\s*\n(?:.|\n)*?schemas:\s*\n((?:.|\n)*)", data)
    # Proto messages and services
    for r, _d, files in os.walk(root):
        for f in files:
            if f.endswith(".proto"):
                data = _read(os.path.join(r, f))
                terms += re.findall(r"message\s+(\w+)", data)
                terms += re.findall(r"service\s+(\w+)", data)
    # Clean up and unique
    flat = []
    for t in terms:
        if isinstance(t, str):
            flat.append(t.strip())
    uniq = sorted(set([t for t in flat if t and len(t) < 100]))
    md = [
        "# Domain Glossary",
        "",
        "_Scaffold generated from OpenAPI paths / schema names and protobuf",
        "messages/services. Entries are **term inventory only** — definitions",
        "are not inferred. Replace scaffold notes with real domain language._",
        "",
    ]
    for t in uniq:
        md.append(f"- **{t}** — _(scaffold: definition not generated)_")
    return "\n".join(md) + "\n"
