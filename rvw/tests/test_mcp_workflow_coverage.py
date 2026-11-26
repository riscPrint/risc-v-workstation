"""Workflow coverage and schema-valid bring-up calls, without native execution."""
import pytest
from jsonschema import Draft202012Validator
from rvw.agent import guide
from rvw.mcp.registry import Registry
from rvw.mcp.profiles import PROFILES, profile_for, workflow_names

pytestmark = pytest.mark.fast


def test_each_tool_has_a_profile_and_workflow():
    registry, problems = Registry.discover()
    assert not problems
    covered = set()
    for workflow in guide.load()['workflows']:
        names = workflow_names(workflow['id'])
        assert names <= registry.tools.keys()
        covered |= names
    assert registry.tools.keys() <= covered
    assert all(profile_for(name) in PROFILES for name in registry.tools)
    assert profile_for('regress_run') == 'core'
    assert profile_for('formal_bmc') == 'formal'
    assert profile_for('replay_pack') == 'debug'


def test_bringup_calls_fit_the_core_profile_and_schema():
    registry, problems = Registry.discover(profile='core')
    assert not problems
    assert len(registry.tools) <= 40
    workflow = guide.select(guide.load(), 'bring-up')['workflows'][0]
    for step in workflow['steps']:
        if not step.get('mcp'):
            continue
        call = step['mcp']
        assert call['tool'] in registry.tools, step['id']
        Draft202012Validator(registry.tools[call['tool']].input_schema).validate(call.get('arguments', {}))
    assert 'doctor_smoke' in registry.tools
    assert 'init_scaffold' in registry.tools


def test_smoke_wrapper_uses_explicit_native_path(monkeypatch):
    from rvw.doctor import mcp_tools
    calls = []
    monkeypatch.setattr(mcp_tools, 'diagnose', lambda **kw: calls.append(kw) or {'status': 'inconclusive'})
    result = mcp_tools._smoke('program.elf', project='project', options='rvfi,wave', platform='platform.json')
    assert result['status'] == 'inconclusive'
    assert calls == [dict(project='project', features='sim,riscv-gcc,cosim', smoke_elf='program.elf',
                          smoke_flags='rvfi,wave', smoke_platform='platform.json', conformance=False)]


def test_scaffold_wrapper_keeps_generation_separate(monkeypatch):
    from rvw.init import mcp_tools, scaffold
    calls = []
    monkeypatch.setattr(scaffold, 'scaffold', lambda path, **kw: calls.append((path, kw)) or {'status': 'planned'})
    assert mcp_tools._scaffold('project', 'rv32i', wire_build=True, dry_run=True)['status'] == 'planned'
    assert calls == [('project', dict(isa='rv32i', wire_build=True, dry_run=True, sbt_project=None, name=None))]
