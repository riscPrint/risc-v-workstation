from types import SimpleNamespace

import pytest

from rvw.formal import slang_capability as probe


@pytest.mark.parametrize('code,output,missing', [
    (0, '', False), (1, 'ERROR: SVA unsupported', True),
    (1, 'ERROR: syntax error', None),
])
def test_probe_preserves_tool_errors(tmp_path, monkeypatch, code, output, missing):
    plugin = tmp_path / 'slang.so'
    plugin.touch()
    monkeypatch.setattr(probe.shutil, 'which', lambda _: '/yosys')
    monkeypatch.setattr(probe, 'run_group', lambda *a, **k: SimpleNamespace(
        returncode=code, stdout=output, stderr=''))
    probe.sva_unavailable.cache_clear()
    try:
        if missing is None:
            with pytest.raises(RuntimeError, match='syntax error'):
                probe.sva_unavailable(str(plugin))
        else:
            reason = probe.sva_unavailable(str(plugin))
            assert bool(reason) == missing
            if reason:
                assert 'SVA unsupported' in reason
                assert 'scripts/install.sh --with-formal' in reason
    finally:
        probe.sva_unavailable.cache_clear()
