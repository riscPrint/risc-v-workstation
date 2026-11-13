"""The OoO model reads C2 traces whose interrupt inputs stay low (an irq levels-0 event)."""
import json
from dataclasses import asdict

import pytest
from test_ooo import cfg, trace
from rvw.ooo.core import run

pytestmark = pytest.mark.fast


def with_irq(path, levels):
    lines = path.read_text().splitlines()
    lines.insert(1, json.dumps({"event": "irq", "cycle": 0, "levels": levels}))
    path.write_text("\n".join(lines) + "\n")


def test_zero_irq_levels_are_not_an_external_event(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(asdict(cfg())))
    plain, low = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    trace(plain)
    trace(low)
    with_irq(low, "0x0")
    assert run(p, low)["cycles"] == run(p, plain)["cycles"]


def test_asserted_irq_levels_stay_unsupported(tmp_path):
    p = tmp_path / "cfg.json"
    p.write_text(json.dumps(asdict(cfg())))
    t = tmp_path / "t.jsonl"
    trace(t)
    with_irq(t, "0x80")
    with pytest.raises(ValueError, match="external events"):
        run(p, t)
