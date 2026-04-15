#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install uv || true
pipx runpip uv install -e ".[dev,examples]" || pip install -e ".[dev,examples]"
echo "Done. Open in VS Code and run the Tour command."
