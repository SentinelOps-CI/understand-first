"""Pack create/publish command implementations (extracted from main.py)."""

from __future__ import annotations

import os
import pathlib

from rich import print

from ucli.pack.publish import make_pack
from ucli.packs.pack import create_pack


def run_pack_create(lens: str, tour: str, contracts: str, o: str) -> None:
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    create_pack(lens, tour, contracts, o)
    print(f"[green]Wrote[/green] {o}")


def run_pack_publish(dist: str = "dist") -> None:
    """Build local understanding-pack.zip artifacts."""
    make_pack(dist)
    print(f"[green]Pack ready in {dist}/[/green]")
