"""Offline cosim check: a matching prefix of a run that did not end is not a match."""
from argparse import Namespace
from types import SimpleNamespace
import pytest
from rvw.cosim import cli

pytestmark = pytest.mark.fast


class Model:
    def close(self):
        pass


@pytest.mark.parametrize("complete,status,code", [(False, "inconclusive", 3), (True, "match", 0)])
def test_offline_prefix_match_is_inconclusive(monkeypatch, tmp_path, complete, status, code):
    inputs = SimpleNamespace(platform=None, shim=None, tool=SimpleNamespace(path=None), child_env={},
                             pythonpath=None, capture=SimpleNamespace(verify_tools=lambda: None),
                             metadata=lambda: {})
    def make(args, directory):
        inputs.args = args
        return inputs
    monkeypatch.setattr(cli, "Inputs", make)
    monkeypatch.setattr(cli, "probe", lambda *a, **k: None)
    monkeypatch.setattr(cli, "Spike", lambda *a, **k: Model())
    monkeypatch.setattr(cli, "check", lambda *a, **k: {"schema": "rvw.cosim/1", "status": "match", "instructions": 5,
        "trace_complete": complete, "scope": "complete trace" if complete else "trace prefix"})
    args = Namespace(cosim_action="check", model="spike", history=10, timeout=120, strict=True, strict_sync=(),
                     trace=tmp_path / "rvfi.jsonl", elf=tmp_path / "a.elf")
    result, exit_code = cli.calculate(args)
    assert (result["status"], exit_code) == (status, code)
    assert result["scope"] == ("complete trace" if complete else "trace prefix")
