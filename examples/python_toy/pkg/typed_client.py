"""Wave 30 fixture client: quoted / Annotated / aliased Optional / Final."""

from __future__ import annotations

from typing import Annotated, Final
from typing import Optional as Opt

from .models import Widget


def via_quoted(obj: "Widget") -> str:  # noqa: UP037  # intentional quoted annotation
    return obj.paint()


def via_annotated(obj: Annotated[Widget, "ui"]) -> str:
    return obj.paint()


def via_opt_alias(obj: Opt[Widget]) -> str:  # noqa: UP045  # intentional Optional alias
    return obj.paint()


def via_final() -> str:
    obj: Final[Widget] = Widget()
    return obj.paint()
