#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install uv || true
pipx runpip uv install -r requirements.txt || pip install -r requirements.txt
(cd cli && pipx runpip uv install -e .) || (cd cli && pip install -e .)
echo "Done. Open in VS Code and run the Tour command." 
