"""Number formatting. Rounds the way a spreadsheet does (half up), not the way Python does
(half to even) - the difference shows up as a phantom mismatch about once per thousand rows."""
from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

DASH = "\u2014"


def _q(v: float, places: str) -> Decimal:
    return Decimal(str(v)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def hours(v: float | None) -> str:
    """2 decimals, trailing zeros trimmed, em dash for blank."""
    if v is None:
        return DASH
    s = format(_q(v, "0.01"), "f").rstrip("0").rstrip(".")
    return s or "0"


def hours_to_add(v: float | None) -> str:
    """Same, but nothing-to-add reads as a dash rather than a zero."""
    return DASH if not v else hours(v)


def pct(v: float | None) -> str:
    return DASH if v is None else f"{_q(v * 100, '1')}%"


def pct1(v: float | None) -> str:
    return DASH if v is None else f"{_q(v * 100, '0.1')}%"


def pair(a: str, b: str) -> str:
    return f"{a} / {b}"


def us_date(d: dt.date) -> str:
    return d.strftime("%m/%d/%Y")
