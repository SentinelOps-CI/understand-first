import re, json, math
from typing import Dict, Any, List, Set, Tuple


def _extract_candidates(issue_text: str) -> List[str]:
    files = re.findall(r"[\w./-]+\.py", issue_text)
    funcs = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\(", issue_text)
    return list(set(files + funcs))


def _neighbors(functions: Dict[str, Any], seed_keys: Set[str], hops: int = 2) -> Dict[str, Any]:
    keep = set()
    for q in functions:
        if any(tok in q for tok in seed_keys):
            keep.add(q)
    for _ in range(hops):
        new = set(keep)
        for q, meta in functions.items():
            if q in keep:
                for callee in meta.get("calls", []):
                    for q2 in functions:
                        if q2.endswith(":" + callee) or callee in q2:
                            new.add(q2)
            else:
                if any(c in q for k in keep for c in functions[k].get("calls", [])):
                    new.add(q)
        keep = new
    return {q: functions[q] for q in keep}


def lens_from_issue(issue_md_path: str, repo_map: Dict[str, Any], hops: int = 2) -> Dict[str, Any]:
    text = open(issue_md_path, "r", encoding="utf-8").read()
    seeds = _extract_candidates(text)
    if not seeds:
        fns = repo_map.get("functions", {})
        ranked = sorted(fns.items(), key=lambda kv: len(kv[1].get("calls", [])), reverse=True)[:10]
        seeds = [k for k, _ in ranked]
    seed_keys = set(seeds)
    lens_funcs = _neighbors(repo_map.get("functions", {}), seed_keys, hops=hops)
    return {"lens": {"seeds": list(seed_keys)}, "functions": lens_funcs}


def lens_from_seeds(seeds: List[str], repo_map: Dict[str, Any], hops: int = 2) -> Dict[str, Any]:
    seed_keys = set(seeds)
    lens_funcs = _neighbors(repo_map.get("functions", {}), seed_keys, hops=hops)
    return {"lens": {"seeds": list(seed_keys)}, "functions": lens_funcs}


def merge_trace_into_lens(lens: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
    hits = {e.get("func") for e in trace.get("events", []) if "func" in e}
    fns = lens.get("functions", {})
    for q in fns:
        name = q.split(":")[-1]
        if name in hits or q in hits:
            fns[q]["runtime_hit"] = True
    lens["runtime"] = {"hit_count": len(hits)}
    return lens


def rank_by_error_proximity(lens: Dict[str, Any]) -> None:
    # score nodes: seed match + runtime hit + distance to seeds (by name similarity)
    seeds = set(lens.get("lens", {}).get("seeds", []))
    fns = lens.get("functions", {})
    for q, meta in fns.items():
        name = q.split(":")[-1]
        score = 0.0
        if any(s in q for s in seeds):
            score += 2.0
        if meta.get("runtime_hit"):
            score += 1.5
        # cheap name overlap with seeds
        for s in seeds:
            if isinstance(s, str):
                common = len(set(name) & set(s)) / (len(set(name) | set(s)) or 1)
                score += 0.5 * common
        meta["error_proximity"] = round(score, 3)


def write_tour_md(lens: Dict[str, Any]) -> str:
    fns = lens.get("functions", {})
    ranked = sorted(fns.items(), key=lambda kv: kv[1].get("error_proximity", 0.0), reverse=True)
    files = []
    for q, meta in ranked:
        if meta.get("file"):
            files.append(meta["file"])
    files = list(dict.fromkeys(files))
    top3 = files[:3]
    seeds = lens.get("lens", {}).get("seeds", [])
    out = ["# 10-minute Task Tour", "", "## Start here (3 files)"]
    out += [f"1. `{p}`" for p in top3]
    out += [
        "",
        "## Invariants to check",
        "- Inputs/outputs on public functions",
        "- Side effects documented (files, network, globals)",
    ]
    out += ["", "## Minimal fixture", "Run the generated fixture (if present) to hit the hot path."]
    out += ["", "## Seeds", ", ".join(seeds)]
    return "\n".join(out)


def explain_node(qname: str, lens: Dict[str, Any], repo_map: Dict[str, Any]) -> Dict[str, Any]:
    fns = repo_map.get("functions", {})
    seeds = set(lens.get("lens", {}).get("seeds", []))
    meta = lens.get("functions", {}).get(qname, {})
    name = qname.split(":")[-1]
    # callers/callees from repo map (by suffix match heuristic)
    callers: List[str] = []
    callees: List[str] = []
    for caller_q, m in fns.items():
        for c in m.get("calls", []):
            if qname.endswith(":" + c) or name == c:
                callers.append(caller_q)
    for c in fns.get(qname, {}).get("calls", []):
        # find qualified
        for cand in fns:
            if cand.endswith(":" + c) or c in cand:
                callees.append(cand)
    callers = list(dict.fromkeys(callers))
    callees = list(dict.fromkeys(callees))

    # distance to any seed by name overlap (cheap heuristic)
    def name_dist(a: str, b: str) -> float:
        sa, sb = set(a), set(b)
        u = len(sa | sb) or 1
        inter = len(sa & sb)
        return 1.0 - inter / u

    distances = [name_dist(name, s.split(":")[-1]) for s in seeds if isinstance(s, str)]
    dist = min(distances) if distances else None

    reason = []
    if dist is not None:
        reason.append({"seed_proximity": {"distance": round(dist, 3)}})
    if meta.get("runtime_hit"):
        reason.append({"runtime_hit": True})
    if "error_proximity" in meta:
        reason.append({"error_proximity": meta.get("error_proximity")})

    return {
        "qname": qname,
        "reason": reason,
        "edges": {
            "callers": callers,
            "callees": callees,
        },
    }
