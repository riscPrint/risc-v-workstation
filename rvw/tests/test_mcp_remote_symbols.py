import pytest

from rvw.mcp.paths import confine
from rvw.mcp.remote import ClientRegistry
from rvw.mcp.spec import ToolError, ToolSpec, schema

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('name,value', [
    ('tasks', ['xor']), ('sbt_project', 'cpu'), ('signal', 'unit/register'),
    ('a', 'unit/input'), ('b', 'unit/output'), ('regex', 'unit/.*'),
])
def test_remote_keeps_symbolic_arguments(tmp_path, name, value):
    shape = {'type': 'array', 'items': {'type': 'string'}} if isinstance(value, list) else {'type': 'string'}
    tool = ToolSpec('fixture_symbols', 'Return symbolic arguments.', schema({name: shape}), lambda **args: args)
    registry = ClientRegistry([tool], project=str(tmp_path))
    try:
        assert registry.call(tool.name, {name: value}) == {name: value}
    finally:
        registry.jobs.shutdown()


@pytest.mark.parametrize('name', ['tasks', 'sbt_project'])
def test_path_like_selectors_still_refuse_escape(tmp_path, name):
    with pytest.raises(ToolError, match='outside'):
        confine({name: '../outside'}, schema({name: {'type': 'string'}}), str(tmp_path))


@pytest.mark.parametrize('metadata', [{'x-rvw-path': True}, {'format': 'path'}])
def test_explicit_path_metadata_overrides_symbolic_names(tmp_path, metadata):
    spec = schema({'signal': {'type': 'string', **metadata}})
    with pytest.raises(ToolError, match='outside'):
        confine({'signal': '../outside'}, spec, str(tmp_path))
    assert confine({'signal': 'inside'}, spec, str(tmp_path)) == {'signal': str(tmp_path / 'inside')}
