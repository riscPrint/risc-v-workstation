import json
from pathlib import Path
import pytest
from rvw.common import dependencies

pytestmark = pytest.mark.fast


def test_invalid_override_is_authoritative(monkeypatch, tmp_path):
    monkeypatch.setenv('RVW_SAIL', str(tmp_path / 'missing'))
    with pytest.raises(ValueError, match='invalid RVW_SAIL'):
        dependencies.resolve('sail', acquire=True)


def test_source_resolution_is_offline_by_default(monkeypatch):
    calls = []
    class Source:
        path = Path('/cache/source')
        rev = 'a' * 40
    def ensure(name, revision, offline):
        calls.append((name, revision, offline))
        return Source()
    monkeypatch.delenv('RISCV_FORMAL', raising=False)
    monkeypatch.setattr(dependencies, 'ensure_pinned_source', ensure)
    assert dependencies.resolve('riscv-formal')['revision'] == 'a' * 40
    assert calls == [('riscv-formal', None, True)]


def test_cli_resolver_outputs_only_path(monkeypatch, capsys):
    from argparse import Namespace
    from rvw.doctor.cli import run
    monkeypatch.setattr(dependencies, 'resolve', lambda *a, **k: {'path': '/cache/source'})
    assert run(Namespace(resolve='act4', acquire=False, json=False)) == 0
    assert capsys.readouterr().out == '/cache/source\n'
