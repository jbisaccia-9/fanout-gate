import json
import shutil

import pytest

from fanoutgate import counterexamples, gate, pipeline, seed, workbook

from conftest import envelope


def test_every_resolvable_lead_passes_and_the_rest_are_skipped_not_guessed(run):
    out, code, text = run
    note = json.loads((out / "run.json").read_text())
    assert code == 0 and note["messages_passing"] == note["messages_built"] == 22
    assert {s["lead"] for s in note["skipped"]} == {seed.AMBIGUOUS, seed.ABSENT}
    assert note["resolved_via_directory"] == 1
    assert not (out / pipeline.slug(seed.AMBIGUOUS)).exists()


def test_no_site_reaches_two_leads(run):
    out, _, _ = run
    from fanoutgate.render import parse
    seen = {}
    for p in out.glob("*/message.html"):
        for row in parse(p.read_text(encoding="utf-8")).rows:
            assert row.site not in seen, f"{row.site} in {seen[row.site]} and {p.parent.name}"
            seen[row.site] = p.parent.name


@pytest.mark.parametrize("name", sorted(counterexamples.DESCRIPTIONS))
def test_counterexample_is_refused_for_exactly_the_rule_in_its_name(data, tmp_path, name):
    counterexamples.build(data, tmp_path / "cx")
    v = gate.grade(tmp_path / "cx" / name, mode="send")
    assert v.rules_failed == [name[:2].upper()], v.failures


def test_stale_week_builds_nothing(data, tmp_path):
    stale = tmp_path / "data"
    shutil.copytree(data, stale)
    (stale / "announcement.json").write_text(json.dumps({"subject": "Site KPI Analysis - 9.20.26"}))
    code, text = pipeline.prepare(stale, tmp_path / "run", tmp_path / "ledger.json")
    assert code == 1 and "G1" in text
    assert list((tmp_path / "run").glob("*/message.html")) == []


def test_missing_announcement_is_not_permission(data, tmp_path):
    d = tmp_path / "data"
    shutil.copytree(data, d)
    (d / "announcement.json").unlink()
    code, _ = pipeline.prepare(d, tmp_path / "run", tmp_path / "ledger.json")
    assert code == 1


def test_workbook_revised_after_build_refuses_the_old_packets(data, tmp_path):
    d = tmp_path / "data"
    shutil.copytree(data, d)
    out = tmp_path / "run"
    assert pipeline.prepare(d, out, tmp_path / "ledger.json")[0] == 0
    seed.write(d, seed=7)                       # upstream republishes the same week
    v = gate.grade(next(out.glob("*/envelope.json")).parent)
    assert "G1" in v.rules_failed


def test_send_is_exactly_once_and_a_revision_reopens_it(data, tmp_path):
    d = tmp_path / "data"
    shutil.copytree(data, d)
    out, ledger = tmp_path / "run", tmp_path / "ledger.json"
    pipeline.prepare(d, out, ledger)
    assert pipeline.send(out)[0] == 0
    assert len(list((out / "outbox").glob("*.html"))) == 22
    code, text = pipeline.send(out)
    assert code == 1 and "sent 0, refused 22" in text
    seed.write(d, seed=7)                       # revised bytes -> new key -> one more send
    pipeline.prepare(d, out, ledger)
    assert pipeline.send(out)[0] == 0


def test_a_partial_run_resumes_without_double_sending(data, tmp_path):
    out, ledger = tmp_path / "run", tmp_path / "ledger.json"
    pipeline.prepare(data, out, ledger)
    pipeline.send(out)
    full = json.loads(ledger.read_text())
    keep = dict(list(full.items())[:10])        # crash after message 10
    ledger.write_text(json.dumps(keep))
    shutil.rmtree(out / "outbox")
    _, text = pipeline.send(out)
    assert "sent 12, refused 10" in text


def test_wrong_address_for_a_resolvable_lead(run):
    out, _, _ = run
    a, b = sorted(out.glob("*/envelope.json"))[:2]
    env = envelope(a.parent)
    env["recipient"] = envelope(b.parent)["recipient"]
    a.write_text(json.dumps(env))
    assert gate.grade(a.parent).rules_failed == ["G2"]


def test_dropped_and_duplicated_rows_are_isolation_failures(run):
    out, _, _ = run
    p = next(out.glob("*/message.html"))
    html = p.read_text(encoding="utf-8")
    rows = html.split("<tr><td")
    p.write_text("<tr><td".join(rows[:-1]) + "</table><p>x</p></div>", encoding="utf-8")
    assert "G3" in gate.grade(p.parent).rules_failed
    p.write_text("<tr><td".join(rows[:2] + rows[1:]), encoding="utf-8")
    assert "G3" in gate.grade(p.parent).rules_failed


def test_a_paraphrased_action_line_is_refused(run):
    out, _, _ = run
    for p in out.glob("*/message.html"):
        html = p.read_text(encoding="utf-8")
        if "Add at least" in html:
            p.write_text(html.replace("Add at least", "Please add", 1), encoding="utf-8")
            assert gate.grade(p.parent).rules_failed == ["G4"]
            return
    pytest.fail("seed produced no QA action line")


@pytest.mark.parametrize("injected", [
    "<p>Overall you are tracking at roughly 6% and need about 14 more hours.</p>",
    "<div>Reminder: target is 12% this month.</div>",
])
def test_commentary_outside_the_three_parts_is_refused(run, injected):
    """Found by probing the gate, not by the gate: both of these passed until G5 learned
    that a message is a greeting, a table and a summary and nothing else."""
    out, _, _ = run
    p = next(out.glob("*/message.html"))
    p.write_text(p.read_text(encoding="utf-8").replace("</table>", "</table>\n" + injected), encoding="utf-8")
    assert gate.grade(p.parent).rules_failed == ["G5"]
