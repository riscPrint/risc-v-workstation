import pytest
from rvw.mcp.paths import confine
from rvw.mcp.registry import Registry, discover
from rvw.mcp.remote import ClientRegistry
from rvw.mcp.spec import ToolSpec, ToolError, schema



@pytest.mark.fast
def test_remote_confinement(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (project / 'escape').symlink_to(outside, target_is_directory=True)
    spec = schema({'db': {'type': 'string'}, 'out': {'type': 'string'}})
    assert confine({'db': 'data.sqlite'}, spec, str(project))['db'] == str(project / 'data.sqlite')
    for value in ('../outside/x', str(outside / 'x'), 'escape/x', 'escape'):
        with pytest.raises(ToolError, match='outside'):
            confine({'db': value}, spec, str(project))
    with pytest.raises(ToolError, match='outside'):
        confine({'unknown': 'escape'}, {}, str(project))
    assert confine({'out': str(outside / 'x')}, spec, str(project), str(outside))['out'] == str(outside / 'x')
    with pytest.raises(ToolError, match='outside'):
        confine({'nested': [{'custom': '../outside'}]}, {}, str(project))


@pytest.mark.fast
def test_all_discovered_string_arguments_are_checked(tmp_path):
    from dataclasses import replace
    tools, problems = discover()
    assert not problems
    def forbidden(**kwargs):
        raise AssertionError('path escape reached a handler')
    registry = ClientRegistry([replace(t, handler=forbidden, long=False) for t in tools], project=str(tmp_path))
    count = 0
    try:
        for tool in tools:
            for name, spec in tool.input_schema.get('properties', {}).items():
                if spec.get('type') in ('string', 'array'):
                    value = ['../escape'] if spec['type'] == 'array' else '../escape'
                    with pytest.raises(ToolError, match='outside|project is fixed'):
                        registry.call(tool.name, {name: value})
                    count += 1
        assert count > 100
        assert registry.jobs.list() == []
    finally:
        registry.jobs.shutdown()


@pytest.mark.fast
def test_remote_dispatch_and_stdio_compatibility(tmp_path):
    tool = ToolSpec('sample', 'sample', schema({'db': {'type': 'string'}}), lambda db: db)
    local = Registry([tool])
    remote = ClientRegistry([tool], project=str(tmp_path))
    try:
        assert local.call('sample', {'db': '/outside'}) == '/outside'
        with pytest.raises(ToolError, match='outside'):
            remote.call('sample', {'db': '/outside'})
        assert remote.call('sample', {'db': 'inside'}) == str(tmp_path / 'inside')
    finally:
        local.jobs.shutdown()
        remote.jobs.shutdown()


def test_sse_paths_and_project_ownership(tmp_path):
    import asyncio
    import json
    from mcp import ClientSession
    from mcp.client.sse import sse_client
    from test_remote_processes import process_server
    projects = [tmp_path / 'alice', tmp_path / 'bob']
    for p in projects:
        p.mkdir()
    policies = tmp_path / 'clients.json'
    policies.write_text(json.dumps({name: {'project': str(project), 'tools': ['evidence_query']}
                                   for name, project in zip(('alice', 'bob'), projects)}))
    async def check(url):
        async with sse_client(url + '/sse', headers={'Authorization': 'Bearer bob'}) as streams:
            async with ClientSession(*streams) as client:
                await client.initialize()
                for db in ('../alice/data.sqlite', str(projects[0] / 'data.sqlite'), '/etc/passwd'):
                    result = await client.call_tool('evidence_query', {'db': db})
                    data = json.loads(result.content[0].text)
                    assert data['status'] == 'error' and 'outside' in data['error']
                result = await client.call_tool('job_list', {})
                assert json.loads(result.content[0].text)['jobs'] == []
    with process_server(tmp_path, ['mcp', '--transport', 'sse', '--clients', str(policies)]) as (url, _):
        asyncio.run(check(url))


@pytest.mark.fast
def test_remote_non_path_strings_keep_their_meaning(tmp_path):
    args = {'image': 'registry.example/team/tool:v1',
            'sail_endpoint': 'http://127.0.0.1:18768',
            'filter': ['^directory/test$'], 'base': 'feature/branch',
            'schema': 'rvw.example/1', 'db': 'design.sqlite'}
    checked = confine(args, {}, str(tmp_path))
    assert checked == {**args, 'db': str(tmp_path / 'design.sqlite')}
