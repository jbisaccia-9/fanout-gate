"""One lead's rows -> one compact HTML message, and the parser that reads it back.

The gate never sees the objects this module was handed. It sees `parse(html)` - what the
recipient will read - and compares that to the workbook."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from html import escape
from html.parser import HTMLParser

from . import fmt
from .resolve import first_name
from .seed import QA_TARGET, TRAIN_TARGET
from .workbook import Site

HEADERS = ["Site", "Service wk/MTD", "QA wk/MTD", "QA % wk/MTD", "+QA hrs",
           "Training wk/MTD", "+Trn hrs", "Action"]
GREEN, RED = "#C6EFCE", "#FFC7CE"
HEAD_FG, HEAD_BG, BODY_FG = "#1F3A5F", "#E6ECF3", "#333333"
FONT = "'Segoe UI',system-ui,sans-serif"   # chat clients strip custom fonts; don't fight it
BULLET = "\u2022 "

# Deliberately small. A roomy table renders enormous in a chat pane.
TD = "padding:1px 4px;border:1px solid #d9d9d9;vertical-align:top;"
NUM = TD + "white-space:nowrap;text-align:right;"


def greeting(lead: str) -> str:
    return f"Hi {first_name(lead)}, here are your current KPI metrics for the week:"


def sort_key(s: Site):
    """Worst first: blanks, then QA % MTD ascending."""
    return (s.qa_pct_mtd is not None, s.qa_pct_mtd or 0.0, s.site)


def cells(s: Site) -> list[str]:
    """The seven non-action cells, exactly as they must appear."""
    return [
        s.site,
        fmt.pair(fmt.hours(s.service_wk), fmt.hours(s.service_mtd)),
        fmt.pair(fmt.hours(s.qa_wk), fmt.hours(s.qa_mtd)),
        fmt.pair(fmt.pct(s.qa_pct_wk), fmt.pct(s.qa_pct_mtd)),
        fmt.hours_to_add(s.qa_add),
        fmt.pair(fmt.hours(s.train_wk), fmt.hours(s.train_mtd)),
        fmt.hours_to_add(s.train_add),
    ]


def summary(rows: list[Site], week: dt.date) -> str:
    service = sum(s.service_mtd or 0 for s in rows)
    qa = sum(s.qa_mtd or 0 for s in rows)
    below = [s for s in rows if s.qa_pct_mtd is not None and s.qa_pct_mtd < QA_TARGET]
    return (f"Week ending {fmt.us_date(week)} \u00b7 Portfolio {len(rows)} \u00b7 "
            f"QA MTD {fmt.hours(qa)} of {fmt.hours(service)} service hours = "
            f"{fmt.pct1(qa / service if service else None)} \u00b7 "
            f"{len(below)} site(s) below 10% MTD needing {fmt.hours(sum(s.qa_add or 0 for s in below))} hours \u00b7 "
            f"Tenant training MTD {fmt.hours(sum(s.train_mtd or 0 for s in rows))} hours, "
            f"{fmt.hours(sum(s.train_add or 0 for s in rows))} hours outstanding")


def _bg(ok: bool | None) -> str:
    return "" if ok is None else f"background:{GREEN if ok else RED};"


def render(lead: str, rows: list[Site], week: dt.date, *,
           action_lines=None, summary_rows: list[Site] | None = None) -> str:
    """`action_lines` and `summary_rows` exist for the counterexamples: they let a packet be
    wrong in exactly one way. The pipeline never passes them."""
    action_lines = action_lines or (lambda s: s.action_lines)
    out = [f'<div style="font-family:{FONT};color:{BODY_FG};">',
           f"<p>{escape(greeting(lead))}</p>",
           f'<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
           f'font-size:11px;line-height:1.15;color:{BODY_FG};">', "<tr>"]
    for h in HEADERS:
        stacked = escape(h).replace(" ", "<br>", 1) if " " in h else escape(h)
        out.append(f'<th style="{TD}font-size:10px;color:{HEAD_FG};background:{HEAD_BG};">{stacked}</th>')
    out.append("</tr>")
    for s in sorted(rows, key=sort_key):
        c = cells(s)
        qa_ok = None if s.qa_pct_mtd is None else s.qa_pct_mtd >= QA_TARGET
        tr_ok = (s.train_mtd or 0) >= TRAIN_TARGET
        styles = [TD, NUM, NUM, NUM + _bg(qa_ok), NUM, NUM + _bg(tr_ok), NUM]
        out.append("<tr>" + "".join(f'<td style="{st}">{escape(v)}</td>' for st, v in zip(styles, c)))
        lines = action_lines(s)
        body = "<br>".join(escape(BULLET + ln) for ln in lines) if lines else fmt.DASH
        out.append(f'<td style="{TD}font-size:10px;">{body}</td></tr>')
    out += ["</table>", f'<p style="font-size:11px;">{escape(summary(summary_rows or rows, week))}</p>', "</div>"]
    return "\n".join(out)


# ---- read-back ---------------------------------------------------------------------------

@dataclass
class ParsedRow:
    cells: list[str]
    bullets: list[str]

    @property
    def site(self) -> str:
        return self.cells[0] if self.cells else ""


@dataclass
class Parsed:
    paragraphs: list[str] = field(default_factory=list)
    headers: list[str] = field(default_factory=list)
    rows: list[ParsedRow] = field(default_factory=list)
    stray: list[str] = field(default_factory=list)   # any text outside <p>, <th>, <td>

    @property
    def greeting(self) -> str:
        return self.paragraphs[0] if self.paragraphs else ""

    @property
    def summary(self) -> str:
        return self.paragraphs[-1] if len(self.paragraphs) > 1 else ""


class _Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.p, self.buf, self.row, self.kind = Parsed(), None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th", "p"):
            self.buf, self.kind = [], tag
        elif tag == "br" and self.buf is not None:
            self.buf.append("\n")

    def handle_data(self, data):
        if self.buf is not None:
            self.buf.append(data)
        elif data.strip():
            self.p.stray.append(data.strip())

    def handle_endtag(self, tag):
        if tag in ("td", "th", "p") and self.buf is not None:
            text = "".join(self.buf).strip()
            self.buf = None
            if tag == "p":
                self.p.paragraphs.append(text)
            elif self.row is not None:
                self.row.append((tag, text))
        elif tag == "tr" and self.row is not None:
            texts = [t for _, t in self.row]
            if self.row and self.row[0][0] == "th":
                self.p.headers = [" ".join(t.split()) for t in texts]
            elif texts:
                action = texts[-1] if len(texts) == len(HEADERS) else ""
                bullets = [] if action in ("", fmt.DASH) else [
                    ln[len(BULLET):] if ln.startswith(BULLET) else ln
                    for ln in action.split("\n") if ln.strip()]
                self.p.rows.append(ParsedRow(texts[:len(HEADERS) - 1], bullets))
            self.row = None


def parse(html: str) -> Parsed:
    r = _Reader()
    r.feed(html)
    return r.p
