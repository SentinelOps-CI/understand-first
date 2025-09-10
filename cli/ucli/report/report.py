from typing import Dict, Any
from collections import Counter

def make_report_md(system_map: Dict[str, Any]) -> str:
    fns = system_map.get('functions', {})
    calls = Counter()
    for q, meta in fns.items():
        for c in meta.get('calls', []):
            calls[c] += 1
    hotspots = calls.most_common(10)
    md = ["# Understanding Report", "", "## Hotspots (most called symbols)"]
    for name, count in hotspots:
        md.append(f"- `{name}` — {count} inbound calls")
    md.append("\n## Next steps\n- Confirm invariants for hotspots.\n- Create/run a minimal fixture on the hot path.")
    return "\n".join(md)

def suggest_fixture(system_map: Dict[str, Any]) -> str:
    return "# Fill a minimal hot-path fixture here (see lens and trace outputs).\n"
