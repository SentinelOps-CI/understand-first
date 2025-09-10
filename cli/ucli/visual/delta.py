import json, html

def _nodes(m): return set(m.get('functions', {}).keys())

def lens_delta_svg(old_path: str, new_path: str) -> str:
    old = json.load(open(old_path, 'r', encoding='utf-8'))
    new = json.load(open(new_path, 'r', encoding='utf-8'))
    old_nodes = _nodes(old); new_nodes = _nodes(new)
    added = new_nodes - old_nodes
    removed = old_nodes - new_nodes
    common = new_nodes & old_nodes

    # simple vertical layout
    items = list(sorted(common)) + list(sorted(added)) + list(sorted(removed))
    h = max(200, 24 * (len(items) + 2))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{h}">']
    y = 20
    svg.append(f'<text x="10" y="{y}" font-size="14" font-weight="bold">Lens delta</text>')
    y += 20
    for q in sorted(common):
        svg.append(f'<text x="20" y="{y}" font-size="12" fill="#444">{html.escape(q)}</text>'); y += 18
    for q in sorted(added):
        svg.append(f'<text x="20" y="{y}" font-size="12" fill="#0a0">+ {html.escape(q)}</text>'); y += 18
    for q in sorted(removed):
        svg.append(f'<text x="20" y="{y}" font-size="12" fill="#a00">- {html.escape(q)}</text>'); y += 18
    svg.append("</svg>")
    return "\n".join(svg)
