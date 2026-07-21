import re
from typing import Any

from ucli.analyzers.map_meta import annotate_lens_from_map


def _extract_candidates(issue_text: str) -> list[str]:
    files = re.findall(r"[\w./-]+\.(?:py|js|mjs|cjs|ts|tsx|jsx)", issue_text)
    funcs = re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\(", issue_text)
    return list(set(files + funcs))


def _seed_matches(q: str, meta: dict[str, Any], seed_keys: set[str], *, exact: bool) -> bool:
    """True when qname/meta matches any seed token.

    Default (exact=False): substring match — ``tok in q`` (historical behavior;
    ``run`` matches ``pkg:Foo.run`` and also ``pkg:runner``).

    exact=True: full qname, local name after ``:``, or ``simple_name`` equality only.
    """
    if exact:
        local = q.rsplit(":", 1)[-1]
        simple = meta.get("simple_name") or local.rsplit(".", 1)[-1]
        return q in seed_keys or local in seed_keys or simple in seed_keys
    return any(tok in q for tok in seed_keys)


def _callee_matches_qn(callee: str, q2: str) -> bool:
    """Match a call token to a function qname without inventing edges.

    Prefers exact qname equality (JS same-file qualified calls), then local-name
    suffix / containment heuristics used historically for Python bare names.
    """
    if callee == q2:
        return True
    if ":" in callee:
        # Already qualified — only exact identity (no substring invention).
        return False
    return q2.endswith(":" + callee) or callee in q2


def _neighbors(
    functions: dict[str, Any],
    seed_keys: set[str],
    hops: int = 2,
    *,
    exact: bool = False,
) -> dict[str, Any]:
    keep = set()
    for q, meta in functions.items():
        if _seed_matches(q, meta, seed_keys, exact=exact):
            keep.add(q)
    for _ in range(hops):
        new = set(keep)
        for q, meta in functions.items():
            if q in keep:
                for callee in meta.get("calls", []):
                    if callee in functions:
                        new.add(callee)
                        continue
                    for q2 in functions:
                        if _callee_matches_qn(str(callee), q2):
                            new.add(q2)
            else:
                for k in keep:
                    for c in functions[k].get("calls", []):
                        if c == q or _callee_matches_qn(str(c), q):
                            new.add(q)
                            break
        keep = new
    return {q: functions[q] for q in keep}


def lens_from_issue(issue_md_path: str, repo_map: dict[str, Any], hops: int = 2) -> dict[str, Any]:
    text = open(issue_md_path, encoding="utf-8").read()
    seeds = _extract_candidates(text)
    if not seeds:
        fns = repo_map.get("functions", {})
        ranked = sorted(fns.items(), key=lambda kv: len(kv[1].get("calls", [])), reverse=True)[:10]
        seeds = [k for k, _ in ranked]
    seed_keys = set(seeds)
    lens_funcs = _neighbors(repo_map.get("functions", {}), seed_keys, hops=hops)
    lens = {"lens": {"seeds": list(seed_keys)}, "functions": lens_funcs}
    return annotate_lens_from_map(lens, repo_map)


def lens_from_seeds(
    seeds: list[str],
    repo_map: dict[str, Any],
    hops: int = 2,
    *,
    exact: bool = False,
) -> dict[str, Any]:
    seed_keys = set(seeds)
    lens_funcs = _neighbors(repo_map.get("functions", {}), seed_keys, hops=hops, exact=exact)
    lens = {
        "lens": {"seeds": list(seed_keys), "exact_match": exact},
        "functions": lens_funcs,
    }
    return annotate_lens_from_map(lens, repo_map)


def merge_trace_into_lens(lens: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    hits = {e.get("func") for e in trace.get("events", []) if "func" in e}
    fns = lens.get("functions", {})
    for q in fns:
        name = q.split(":")[-1]
        if name in hits or q in hits:
            fns[q]["runtime_hit"] = True
    lens["runtime"] = {"hit_count": len(hits)}
    return lens


def rank_by_error_proximity(lens: dict[str, Any]) -> None:
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


def write_tour_md(lens: dict[str, Any]) -> str:
    fns = lens.get("functions", {})
    ranked = sorted(fns.items(), key=lambda kv: kv[1].get("error_proximity", 0.0), reverse=True)
    files = []
    for _q, meta in ranked:
        if meta.get("file"):
            files.append(meta["file"])
    files = list(dict.fromkeys(files))
    top3 = files[:3]
    seeds = lens.get("lens", {}).get("seeds", [])
    fidelity = lens.get("lens", {}).get("fidelity") or lens.get("analyzer_fidelity")
    complexity_note = lens.get("lens", {}).get("complexity_note")
    language = lens.get("language") or lens.get("lens", {}).get("language")
    out = ["# 10-minute Task Tour", "", "## Start here (3 files)"]
    out += [f"1. `{p}`" for p in top3]
    out += [
        "",
        "## Invariants to check",
        "- Inputs/outputs on public functions",
        "- Side effects documented (files, network, globals)",
    ]
    out += ["", "## Minimal fixture", "Run the generated fixture (if present) to hit the hot path."]
    out += ["", "## Seeds", ", ".join(str(s) for s in seeds)]
    # Honesty: JS/TS lenses are structural only — no Python tour_run parity.
    out += ["", "## Map fidelity"]
    if language:
        out.append(f"- Language: `{language}`")
    if isinstance(fidelity, dict):
        out.append(f"- Analyzer fidelity: `{fidelity}`")
    elif fidelity:
        out.append(f"- Analyzer fidelity: `{fidelity}`")
    if complexity_note:
        out.append(f"- {complexity_note}")
    if language in {"javascript", "typescript"} or (
        isinstance(fidelity, str) and fidelity == "best-effort"
    ):
        out.append(
            "- Runtime `u trace` / `u tour_run` are Python-only; this tour is a reading plan "
            "from a best-effort map, not CLI runtime parity."
        )
    elif language in {"go", "java", "rust", "csharp"}:
        out.append(
            f"- Language `{language}`: structural/best-effort map only; "
            "`u trace` / `u tour_run` remain Python-only."
        )
    elif language == "mixed":
        out.append(
            "- Mixed map: Python subsets may support `u trace`; other languages are "
            "map/reading-plan only."
        )
    return "\n".join(out)


def explain_node(qname: str, lens: dict[str, Any], repo_map: dict[str, Any]) -> dict[str, Any]:
    fns = repo_map.get("functions", {})
    seeds = set(lens.get("lens", {}).get("seeds", []))
    meta = lens.get("functions", {}).get(qname, {})
    name = qname.split(":")[-1]
    # callers/callees from repo map (prefer exact qnames on JS maps)
    callers: list[str] = []
    callees: list[str] = []
    for caller_q, m in fns.items():
        for c in m.get("calls", []):
            if c == qname or _callee_matches_qn(str(c), qname) or name == c:
                callers.append(caller_q)
    for c in fns.get(qname, {}).get("calls", []):
        if c in fns:
            callees.append(c)
            continue
        for cand in fns:
            if _callee_matches_qn(str(c), cand):
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
