# Onboarding (10-minute tour)

Follow these steps to build understanding artifacts for this repository.

1) Install and bootstrap
```bash
pip install -e cli
```

2) Build a repository map
```bash
u scan . -o maps/repo.json
```

3) Create a task lens from seeds
```bash
u lens from-seeds --map maps/repo.json --seed examples/app/hot_path.py -o maps/lens.json
```

4) Trace the hot path (Python demo)
```bash
u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json
```

5) Merge trace into lens and rank by error proximity
```bash
u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json
```

6) Generate a tour
```bash
u tour maps/lens_merged.json -o tours/local.md
```

7) Open VS Code to view overlays and the tour
- Use the command: Understand-First: Show Tour
- Open the three suggested files and run the buttons in order

## Health check
```bash
u doctor
```
Verifies Python/Node, grpc_tools, VS Code, ports, and repo write permissions.

## Guided demo
```bash
u demo
```
Generates contracts, starts the sample HTTP server, traces the hot path, builds a tour and dashboard, and prints a local file URL.

## Screenshots and demo
- Editor overlay: gutter badges and CodeLens in VS Code
- PR comment: Tour, Delta, and Dashboard
- Short walkthrough GIF (optional)
