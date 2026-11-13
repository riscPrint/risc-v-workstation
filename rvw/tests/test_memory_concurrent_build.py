import json
from types import SimpleNamespace
import pytest
import rvw.memory.concurrent_build as module
from rvw.memory.commands.concurrent_build import mcp_tools

pytestmark = pytest.mark.fast


def test_missing_compiler_does_not_create_output(tmp_path, monkeypatch):
    monkeypatch.setattr(module.shutil, 'which', lambda tool: None)
    report=module.build(tmp_path/'absent')
    assert report['status']=='inconclusive' and not report['executed']
    assert not (tmp_path/'absent').exists()


@pytest.mark.parametrize('fields', [dict(base=1), dict(shared_base=1),
                                   dict(shared_base=0x80000000), dict(base=(1 << 64)-4096),
                                   dict(timeout=61), dict(harts=1)])
def test_unsupported_layout_or_budget_fails_before_build(tmp_path, fields):
    with pytest.raises(ValueError):
        module.build(tmp_path/'bad', **fields)
    assert not (tmp_path/'bad').exists()


def test_failed_compile_records_no_execution_and_does_not_clobber(tmp_path, monkeypatch):
    monkeypatch.setattr(module.shutil, 'which', lambda tool: '/compiler')
    commands=[]
    def fail(command, **kw):
        commands.append((command, kw))
        return SimpleNamespace(returncode=1, timed_out=False, stdout='', stderr='seeded compile failure')
    monkeypatch.setattr(module, 'run_group', fail)
    root=tmp_path/'failed'
    report=module.build(root, seed=7, harts=3, length=20)
    assert report['status']=='inconclusive' and report['reason']=='compile failed'
    assert report==json.loads((root/'build.json').read_text())
    assert not (root/'hart-images.json').exists()
    assert commands[0][0][:3]==['nice', '-n', '10']
    assert 0 < commands[0][1]['timeout'] <= 30
    with pytest.raises(FileExistsError):
        module.build(root)


def test_total_budget_is_not_restarted_for_each_hart(tmp_path, monkeypatch):
    monkeypatch.setattr(module.shutil, 'which', lambda tool: '/compiler')
    times=iter([0, 31])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(times))
    monkeypatch.setattr(module, 'run_group', lambda *a, **k: pytest.fail('expired compiler launched'))
    report=module.build(tmp_path/'expired')
    assert report['status']=='inconclusive' and report['completed_harts']==0


def test_mcp_command_uses_the_builder_and_exposes_output():
    tools=mcp_tools()
    assert len(tools)==1 and tools[0].name=='memory_concurrent_build'
