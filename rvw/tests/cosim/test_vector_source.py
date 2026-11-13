from types import SimpleNamespace
import pytest
from rvw.cosim import vector_source as source


def test_prepare_pins_both_sources(tmp_path, monkeypatch):
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        if args[1] == 'clone':
            from pathlib import Path
            Path(args[-1]).mkdir(parents=True)
        revision = source.ENV_REVISION if 'env/riscv-test-env' in args[2] else source.REVISION
        return SimpleNamespace(timed_out=False, returncode=0, stdout=revision, stderr='')
    monkeypatch.setattr(source, 'run_group', run)
    result = source.fetch(tmp_path/'external')
    assert result['revision'] == source.REVISION
    assert not result['built']
    assert len(calls) == 6
    assert not any('submodule' in args for args in calls)


def test_refuse_inside_repository():
    with pytest.raises(ValueError, match='outside'):
        source.fetch(source.ROOT/'vendor-vector')


@pytest.fixture
def tmp_path(external_tmp_path):
    return external_tmp_path
