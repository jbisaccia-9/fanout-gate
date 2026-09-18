import datetime as dt

from fanoutgate import fmt, reconcile, workbook
from fanoutgate.gate import announced_week
from fanoutgate.resolve import resolve


def test_rounds_like_a_spreadsheet_not_like_python():
    assert round(2.675, 2) == 2.67          # the trap
    assert fmt.hours(2.675) == "2.68"
    assert fmt.hours(27.0) == "27" and fmt.hours(2.50) == "2.5" and fmt.hours(0) == "0"
    assert fmt.hours(None) == fmt.DASH and fmt.hours_to_add(0) == fmt.DASH
    assert fmt.pct(0.105) == "11%" and fmt.pct(None) == fmt.DASH


def test_announcement_subject_carries_the_week():
    assert announced_week({"subject": "Site KPI Analysis - 9.13.26"}) == dt.date(2026, 9, 13)
    assert announced_week({"subject": "Re: lunch"}) is None


def test_resolution_order_and_refusals():
    ids, roster = {"Abara Imani": "E1"}, {"E1": "imani@x.example"}
    d = [{"name": "Imani Abara", "email": "other@x.example"},
         {"name": "Ana Ruiz", "email": "a1@x.example"}, {"name": "Ana Ruiz", "email": "a2@x.example"},
         {"name": "Kenji Ueda", "email": "k@x.example"}]
    assert resolve("Abara Imani", ids, roster, d).address == "imani@x.example"   # roster beats directory
    assert resolve("Ueda Kenji", ids, roster, d).via == "directory"
    assert resolve("Ruiz Ana", ids, roster, d).status == "ambiguous"
    assert resolve("Nobody Here", ids, roster, d).status == "unresolved"


def test_reads_by_column_number_under_a_two_row_header(data):
    wb = workbook.read(workbook.find_workbook(data))
    assert wb.week_ending == wb.filename_week == dt.date(2026, 9, 13)
    assert len(wb.sites) == 203 and len(wb.by_lead()) == 24 and len(wb.lead_ids) == 21
    assert all(s.site_id.startswith("S-") for s in wb.sites)


def test_documented_formula_does_not_reproduce_the_stored_text(data):
    r = reconcile.report(workbook.read(workbook.find_workbook(data)))
    assert r["rows_exact"] < r["rows"]
    assert r["training_lines_reproduced"] < r["training_lines"]
    assert r["order_only_mismatches"] > 0
