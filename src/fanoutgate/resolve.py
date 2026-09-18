"""Recipient resolution. A wrong recipient means one lead reads another lead's portfolio,
so the only acceptable outcomes are 'exactly one address' and 'skip and report'."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Resolution:
    lead: str
    status: str                      # resolved | ambiguous | unresolved
    address: str | None = None
    via: str | None = None           # roster | directory
    candidates: list[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        if self.status == "ambiguous":
            return f"{len(self.candidates)} directory matches ({', '.join(self.candidates)})"
        if self.status == "unresolved":
            return "not in Lead View and no directory match"
        return f"resolved via {self.via}"


def _norm(name: str) -> str:
    return " ".join(sorted(name.lower().replace(",", " ").split()))


def first_name(lead: str) -> str:
    """Workbook names are 'Last First'."""
    parts = lead.split(" ", 1)
    return parts[1] if len(parts) == 2 else lead


def resolve(lead: str, lead_ids: dict[str, str], roster: dict[str, str],
            directory: list[dict]) -> Resolution:
    # (a) the workbook's own Lead View -> employee id -> HR roster. Exact, keyed on an id.
    emp = lead_ids.get(lead)
    if emp and roster.get(emp):
        return Resolution(lead, "resolved", roster[emp], "roster")
    # (b) the directory, by name. Names collide, so more than one hit is not a hit.
    hits = [e["email"] for e in directory if _norm(e["name"]) == _norm(lead)]
    if len(hits) == 1:
        return Resolution(lead, "resolved", hits[0], "directory")
    if len(hits) > 1:
        return Resolution(lead, "ambiguous", candidates=hits)
    return Resolution(lead, "unresolved")
