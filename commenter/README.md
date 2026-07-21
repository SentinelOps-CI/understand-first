# Understand-First PR Commenter (thin path)

**Status:** This directory is **not** a production-ready microservice.
Legacy webhook/Docker/k8s assets lived a false `u analyze` + invented-metrics
life; they are archived under `legacy/` and must not be deployed as-is.

## What is real today

Use the GitHub Actions thin path instead:

- Workflow: `.github/workflows/understand-first-pr-analysis.yml`
- Commands: `pip install -e .` then `u scan` + `u diff --old/--new --json`
- Artifacts: `maps/repo_base.json`, `maps/repo_head.json`, `maps/delta.json`

`understand_first_commenter.py` is a **thin wrapper** around those same
commands. It posts a markdown summary from real `delta.json` fields only
(added/removed/modified, complexity net change, heuristic side-effect tag diffs,
policy breaches). It does **not** claim mini-maps, risk scores, or hot-path theater.

## Thin local usage

```bash
pip install -e .
pip install -r commenter/requirements.txt   # requests only

export GITHUB_TOKEN=...
python commenter/understand_first_commenter.py \
  --repository owner/repo \
  --pr-number 123 \
  --base-sha <base> \
  --head-sha <head>
```

Requires git checkout access to both SHAs and the `u` CLI on PATH.

## Quarantined / do not use without rewrite

| Asset | Note |
|-------|------|
| `legacy/webhook_handler.py` | Legacy webhook surface; not wired to thin path |
| `legacy/Dockerfile` / `legacy/k8s-deployment.yaml` | Dead until revalidated |
| `.github/workflows/understand-first-commenter.yml` | Intentionally disabled |

## License

MIT — see repository LICENSE.
