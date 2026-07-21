# Instrumentation (orphan experiment)

**Status:** This directory is a **standalone / orphan** metrics experiment. It is
**not** imported by the `u` CLI, not installed via root package extras, and not
required for maps, tours, or CI analysis. Treat it like `commenter/legacy/`:
optional local experiments only - not a platform product surface.

For the main product, install from the **repository root**
(`uv sync --all-extras` or `pip install -e ".[dev,examples]"`).

## What this is

A small local toolkit under this folder (`requirements.txt`, optional Docker) for
opt-in event logging experiments. Scripts and APIs here are **not** wired into
`u scan`, GitHub Actions thin paths, or the VS Code extension shipping path.

## What this is not

- Not a KPI / TTU / TTFSC product dashboard for Understand-First
- Not rage-click or funnel analytics tied to the CLI
- Not something CI or `pip install understand-first` enables

## Local experiment (optional)

If you intentionally want to run the orphan stack:

```bash
cd instrumentation
pip install -r requirements.txt
# then run whatever entrypoint exists in this folder for your experiment
```

Expect breakage, missing wiring, and no support commitment. Prefer root-level
`metrics/` event logs only when you opt in via documented CLI flags - those are
separate from this directory.

## Quarantine

Do not document this folder as part of onboarding, release notes, or "platform"
features. If a metric matters to the product, it belongs in the root CLI/docs
with honest scope - not here.
