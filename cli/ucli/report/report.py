from collections import Counter
from typing import Any

from ucli.analyzers.map_meta import complexity_semantics_note, map_fidelity_label


def make_report_md(system_map: dict[str, Any]) -> str:
    fns = system_map.get("functions", {})
    calls = Counter()
    for _q, meta in fns.items():
        for c in meta.get("calls", []):
            calls[c] += 1
    hotspots = calls.most_common(10)
    md = ["# Understanding Report", ""]

    analyzer = system_map.get("analyzer")
    kind = system_map.get("complexity_kind")
    fidelity = map_fidelity_label(system_map)
    md.append("## Map fidelity")
    md.append(f"- Language: `{system_map.get('language', 'unknown')}`")
    if analyzer:
        md.append(f"- Analyzer: `{analyzer}`")
    md.append(f"- Fidelity: `{fidelity}`")
    if kind:
        md.append(f"- Complexity kind: `{kind}`")
    md.append(f"- {complexity_semantics_note(system_map)}")
    md.append("")

    md.append("## Hotspots (most called symbols)")
    for name, count in hotspots:
        md.append(f"- `{name}` — {count} inbound calls")

    # High-confidence concrete class returns (factory → obj.method edges when unique).
    typed_returns = sorted(
        (qn, meta["return_type"])
        for qn, meta in fns.items()
        if isinstance(meta.get("return_type"), str) and meta["return_type"]
    )
    if typed_returns:
        md.append("")
        md.append("## Inferred return types (high-confidence)")
        md.append(
            "Concrete class names used for `obj = factory(); obj.method` edges when "
            "uniquely gated (including imported / `mod.Class` origins). "
            "Ambiguous or multi-return factories omit `return_type`."
        )
        for qn, rt in typed_returns[:25]:
            md.append(f"- `{qn}` → `{rt}`")
        if len(typed_returns) > 25:
            md.append(f"- … and {len(typed_returns) - 25} more")

    md.append(
        "\n## Next steps\n- Confirm invariants for hotspots.\n- Create/run a minimal fixture on the hot path."
    )
    return "\n".join(md)


def suggest_fixture(system_map: dict[str, Any]) -> str:
    return "# Fill a minimal hot-path fixture here (see lens and trace outputs).\n"
