import pytest
from rvw.mcp.aliases import with_aliases
from rvw.mcp.audit import audit
from rvw.mcp.registry import Registry
from rvw.mcp.spec import ToolSpec, schema

pytestmark = pytest.mark.fast


def test_canonical_and_legacy_names_reach_same_handler():
    tool = with_aliases(ToolSpec('test_alias', 'Read a selected database.',
        schema({'db_path': {'type': 'string'}}, ['db_path']),
        lambda db_path: {'db': db_path}), db='db_path')
    registry = Registry([tool])
    assert registry.call('test_alias', {'db': 'input'}) == {'db': 'input'}
    assert registry.call('test_alias', {'db_path': 'input'}) == {'db': 'input'}
    for arguments in ({}, {'db': 'a', 'db_path': 'b'}, {'db': 3}):
        _, result, error = registry.call_json('test_alias', arguments)
        assert error and result['code'] == 'invalid_arguments'
    assert registry.call('test_alias', {}, dry_run=True)['dry_run']
    assert not any(f['code'] == 'argument_alias' for r in audit(registry)['tools'] for f in r['findings'])


def test_boolean_run_is_an_execution_flag():
    registry = Registry([ToolSpec('test_run', 'Optionally execute a check.',
        schema({'run': {'type': 'boolean'}}), lambda run=False: run)])
    assert not any(f['code'] == 'argument_alias' for r in audit(registry)['tools'] for f in r['findings'])


def test_provider_aliases_are_explicit_and_optional():
    registry, problems = Registry.discover()
    assert not problems
    for name in ('soc_audit', 'soc_feedback', 'soc_handoff', 'soc_mbist', 'farm_dashboard'):
        tool = registry.tools[name]
        canonical, old = ('run_id', 'run') if name == 'farm_dashboard' else ('db', 'db_path')
        assert canonical in tool.input_schema['properties']
        assert tool.input_schema['properties'][old]['x-alias-for'] == canonical
        arguments = {k: 'fixture' for k in tool.input_schema['required']}
        for key in (canonical, old):
            registry._validators[name].validate({**arguments, key: 'fixture'})
