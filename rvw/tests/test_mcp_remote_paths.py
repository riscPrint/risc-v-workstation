import pytest
from rvw.mcp.paths import confine, is_path
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
def test_all_discovered_path_properties_are_checked(tmp_path):
    tools, problems = discover()
    assert not problems
    count = 0
    for tool in tools:
        for name, spec in tool.input_schema.get('properties', {}).items():
            if is_path(name, spec) and spec.get('type') in ('string', 'array'):
                value = ['../escape'] if spec['type'] == 'array' else '../escape'
                with pytest.raises(ToolError, match='outside'):
                    confine({name: value}, tool.input_schema, str(tmp_path))
                count += 1
    assert count > 100


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
