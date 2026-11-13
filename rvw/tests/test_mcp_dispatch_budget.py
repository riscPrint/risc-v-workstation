"""Known providers must not rediscover the catalog on an isolated call."""
import pytest

pytestmark = pytest.mark.fast


def test_worker_resolves_known_provider_without_discovery(monkeypatch):
    from rvw.mcp import execution, registry
    from rvw.mcp.spec import ToolSpec, schema
    import types
    calls = []
    module = types.SimpleNamespace(mcp_tools=lambda: [ToolSpec(
        'tiny', 'tiny', schema({}), lambda: calls.append('handler') or {'value': 1})])
    from rvw.mcp import lazy
    monkeypatch.setattr(lazy, 'import_module', lambda name: module if name == 'test_provider' else None)
    monkeypatch.setattr(registry, 'discover', lambda *a: pytest.fail('catalog rediscovery'))
    assert execution.run_discovered('tiny', {}, provider='test_provider') == {'value': 1}
    assert calls == ['handler']


def test_discovered_isolation_keeps_provider_without_importing_handler(monkeypatch):
    from rvw.mcp.registry import Registry, _provided
    from rvw.mcp.spec import ToolSpec, schema
    tool = ToolSpec('wave_tiny', 'tiny', schema({}), lambda: 1)
    _provided('test_provider', [tool])
    registry = Registry([tool])
    assert registry._isolated(tool) == ('rvw.mcp.execution', 'run_discovered')
    registry.jobs.shutdown()


def test_long_wrapper_checks_signature_once(monkeypatch):
    from rvw.mcp.spec import ToolSpec, schema
    import rvw.mcp.spec as module
    calls = []
    signature = module.inspect.signature
    monkeypatch.setattr(module.inspect, 'signature',
                        lambda handler: (calls.append(handler), signature(handler))[1])
    tool = ToolSpec('tiny', 'tiny', schema({}), lambda job: None, long=True)
    assert tool.wants_job
    assert tool.wants_job
    assert len(calls) == 1


def test_empty_arguments_do_not_need_json_serialization(monkeypatch):
    from rvw.mcp import registry
    from rvw.mcp.spec import ToolSpec, schema, ToolError
    tool = ToolSpec('tiny', 'tiny', schema({'value': {'type': 'number'}}),
                    lambda **kw: kw)
    instance = registry.Registry([tool])
    instance.call('tiny', {})  # Load and check the schema before the measurement.
    calls = []
    dumps = registry.json.dumps
    monkeypatch.setattr(registry.json, 'dumps',
                        lambda *a, **k: (calls.append(1), dumps(*a, **k))[1])
    assert instance.call('tiny', {}) == {}
    assert not calls
    with pytest.raises(ToolError):
        instance.call('tiny', {'value': float('nan')})
    assert calls
    instance.jobs.shutdown()
