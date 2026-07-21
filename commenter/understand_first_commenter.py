#!/usr/bin/env python3
"""Thin PR commenter backed by real `u scan` + `u diff` artifacts (Wave 3).

Does not call `u analyze`. Does not invent risk scores or undocumented metrics.
Legacy webhook/Docker/k8s assets live under commenter/legacy/ — see README.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import requests


def _run(cmd: list[str], cwd: str | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=cwd)


def scan_and_diff(repo_root: Path, base_sha: str, head_sha: str, out_dir: Path) -> Path:
    """Checkout SHAs, scan maps, write delta.json. Returns delta path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    head_map = out_dir / "repo_head.json"
    base_map = out_dir / "repo_base.json"
    delta_path = out_dir / "delta.json"

    _run(["git", "checkout", "--force", head_sha], cwd=str(repo_root))
    _run(["u", "scan", ".", "-o", str(head_map)], cwd=str(repo_root))

    _run(["git", "checkout", "--force", base_sha], cwd=str(repo_root))
    _run(["u", "scan", ".", "-o", str(base_map)], cwd=str(repo_root))

    _run(["git", "checkout", "--force", head_sha], cwd=str(repo_root))
    _run(
        [
            "u",
            "diff",
            "--old",
            str(base_map),
            "--new",
            str(head_map),
            "-o",
            str(delta_path),
            "--json",
        ],
        cwd=str(repo_root),
    )
    return delta_path


def format_comment(delta: dict[str, Any]) -> str:
    s = delta.get("summary") or {}
    cd = delta.get("complexity_delta") or {}
    net = s.get("complexity_net_change", cd.get("net_change", 0))
    sign = "+" if int(net) >= 0 else ""
    lines = [
        "## Understand-First PR map delta",
        "",
        "| Metric | Value |",
        "|--------|------:|",
        f"| Functions added | {s.get('added', 0)} |",
        f"| Functions removed | {s.get('removed', 0)} |",
        f"| Functions modified | {s.get('modified', 0)} |",
        f"| Complexity net change | {sign}{net} |",
        f"| Side-effect tag adds (heuristic) | {s.get('side_effects_added', 0)} |",
        f"| Policy breaches | {s.get('policy_breaches', 0)} |",
        "",
        "_From `u scan` + `u diff --old/--new`. Side effects are AST heuristics._",
    ]
    breaches = delta.get("policy_breaches") or []
    if breaches:
        lines.append("")
        lines.append("### Policy breaches")
        for b in breaches[:12]:
            lines.append(
                f"- `{b.get('function')}`: {b.get('old_complexity')} → "
                f"{b.get('new_complexity')} (threshold {b.get('threshold')})"
            )
    return "\n".join(lines) + "\n"


def post_or_update_comment(
    token: str, repository: str, pr_number: int, body: str
) -> None:
    owner, repo = repository.split("/", 1)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "understand-first-thin-commenter",
    }
    comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    resp = requests.get(comments_url, headers=headers, timeout=30)
    resp.raise_for_status()
    existing = next(
        (c for c in resp.json() if "Understand-First PR map delta" in c.get("body", "")),
        None,
    )
    if existing:
        patch_url = (
            f"https://api.github.com/repos/{owner}/{repo}/issues/comments/{existing['id']}"
        )
        r = requests.patch(patch_url, headers=headers, json={"body": body}, timeout=30)
        r.raise_for_status()
        print("Updated existing comment")
    else:
        r = requests.post(comments_url, headers=headers, json={"body": body}, timeout=30)
        r.raise_for_status()
        print("Created comment")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Thin Understand-First PR commenter")
    p.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN"))
    p.add_argument("--repository", required=True, help="owner/repo")
    p.add_argument("--pr-number", type=int, required=True)
    p.add_argument("--base-sha", required=True)
    p.add_argument("--head-sha", required=True)
    p.add_argument(
        "--repo-root",
        default=".",
        help="Git working tree to scan (default: cwd)",
    )
    p.add_argument(
        "--delta-json",
        default="",
        help="Skip scan/diff and comment from an existing delta.json",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print markdown only; do not post",
    )
    args = p.parse_args(argv)

    if args.delta_json:
        delta = json.loads(Path(args.delta_json).read_text(encoding="utf-8"))
    else:
        out = Path(tempfile.mkdtemp(prefix="uf-commenter-"))
        delta_path = scan_and_diff(
            Path(args.repo_root).resolve(), args.base_sha, args.head_sha, out
        )
        delta = json.loads(delta_path.read_text(encoding="utf-8"))

    body = format_comment(delta)
    if args.dry_run or not args.github_token:
        print(body)
        if not args.github_token and not args.dry_run:
            print("No GITHUB_TOKEN; dry-run only", file=sys.stderr)
        return 0

    post_or_update_comment(args.github_token, args.repository, args.pr_number, body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
