# Legacy commenter packaging (quarantined)

These files are **not** part of the supported thin PR-comment path.

| File | Why quarantined |
|------|-----------------|
| `webhook_handler.py` | Flask webhook surface; not wired to `u scan` / `u diff` |
| `Dockerfile` | Built the old invent-metrics service |
| `k8s-deployment.yaml` | Assumed the dead Docker image |

Do not deploy. Prefer `.github/workflows/understand-first-pr-analysis.yml` and
`commenter/understand_first_commenter.py` (thin wrapper).
