import json
from pathlib import Path

import pytest

from fanoutgate import pipeline, seed


@pytest.fixture(scope="session")
def data(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("data")
    seed.write(d)
    return d


@pytest.fixture()
def run(data, tmp_path):
    out = tmp_path / "run"
    code, text = pipeline.prepare(data, out, tmp_path / "ledger.json")
    return out, code, text


def envelope(packet: Path) -> dict:
    return json.loads((packet / "envelope.json").read_text())
