import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CLI = ROOT / "cli"
for _p in (ROOT, CLI):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
