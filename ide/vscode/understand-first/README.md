Adds gutter badges for callers and runtime hotness, shows tours, and a basic error propagation explainer.

## Features
- Editor decorations: call counts, runtime hotness, and contract presence when `maps/*` and a lens are available.
- Tour Walkthrough webview with one‑click commands to trace, merge, and generate a tour.
- Property test scaffolding with language‑aware strategies.
- Quick access to the glossary.

## Commands
- Understand-First: Show Tour
- Understand-First: Explain Error Propagation
- Understand-First: Generate Property Test
- Understand-First: Open Glossary

## Setup
1) Generate maps and a lens using the CLI:
```bash
u scan . -o maps/repo.json
u lens from-seeds --map maps/repo.json --seed examples/app/hot_path.py -o maps/lens.json
u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json
u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json
```
2) Open VS Code in the repository and run: Understand-First: Show Tour
