import json, os
from typing import Dict, Any

def build_dashboard(paths: Dict[str,str]) -> str:
    repo = json.load(open(paths.get('repo',''), 'r', encoding='utf-8')) if os.path.exists(paths.get('repo','')) else {}
    lens = json.load(open(paths.get('lens',''), 'r', encoding='utf-8')) if os.path.exists(paths.get('lens','')) else {}
    bounds = json.load(open(paths.get('bounds',''), 'r', encoding='utf-8')) if os.path.exists(paths.get('bounds','')) else {}
    lines = ["# Understanding Dashboard", ""]
    lines.append(f"- Functions mapped: {len(repo.get('functions', {}))}")
    lines.append(f"- Lens nodes: {len(lens.get('functions', {}))}")
    rt = lens.get('runtime', {}).get('hit_count', 0)
    lines.append(f"- Runtime hits: {rt}")
    lines.append("")
    lines.append("## Boundaries")
    for k in ('openapi_paths','proto_rpcs','sql_tables'):
        if bounds.get(k):
            lines.append(f"- {k}: {len(bounds[k])}")
    lines.append("")
    lines.append("## Artifacts")
    for label, p in paths.items():
        if p and os.path.exists(p):
            lines.append(f"- {label}: `{p}`")
    return "\n".join(lines) + "\n"
