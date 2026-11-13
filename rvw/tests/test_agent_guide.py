"""Agent playbook: data validity, CLI paths, MCP names, generated doc block, MCP resource."""
import json
import os
import sys
from pathlib import Path

import anyio
import pytest

from rvw.agent import guide
from rvw.cli import build_parser
from rvw.mcp.registry import Registry

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = {'bring-up', 'test-fails', 'add-coverage', 'prove-property', 'performance-question'}


def test_playbook_is_valid_and_complete():
    data = guide.load()
    assert {w['id'] for w in data['workflows']} == WORKFLOWS
    assert guide.validate(data) == []
    broken = json.loads(json.dumps(data))
    broken['workflows'][0]['steps'][0]['decide'][0]['then'] = 'nowhere'
    assert any('nowhere' in p for p in guide.validate(broken))


def test_every_cli_step_parses_and_every_mcp_tool_exists():
    parser = build_parser()
    registry, _ = Registry.discover()
    for workflow in guide.load()['workflows']:
        for step in workflow['steps']:
            if step.get('cli'):
                args = parser.parse_args(step['cli'])
                assert callable(args.func), step['id']
            if step.get('mcp'):
                assert step['mcp']['tool'] in registry.tools, (workflow['id'], step['mcp']['tool'])
    assert registry.read_resource('rvw://agent/guide').startswith('{')
    assert json.loads(registry.read_resource('rvw://agent/guide/test-fails'))['workflows'][0]['id'] == 'test-fails'


def test_agent_setup_embeds_the_generated_block():
    text = (ROOT / 'docs/AGENT_SETUP.md').read_text()
    assert guide.markdown() in text, 'run: rvw agent guide --markdown --write docs/AGENT_SETUP.md'
    assert guide.embed(text, guide.markdown()) == text


def test_guide_cli_json_and_unknown_workflow(capsys):
    from rvw.cli import main
    assert main(['agent', 'guide', '--workflow', 'prove-property', '--json']) == 0
    out = json.loads(capsys.readouterr().out)
    assert [w['id'] for w in out['workflows']] == ['prove-property']
    with pytest.raises(ValueError):
        guide.select(guide.load(), 'missing')


def test_guide_resource_over_mcp_stdio():
    pytest.importorskip('mcp')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=['-m', 'rvw', 'mcp'], env=dict(os.environ))

    async def session():
        async with stdio_client(params) as streams:
            async with ClientSession(streams[0], streams[1]) as s:
                await s.initialize()
                uris = {str(r.uri) for r in (await s.list_resources()).resources}
                assert 'rvw://agent/guide' in uris and 'rvw://agent/guide/bring-up' in uris
                body = await s.read_resource('rvw://agent/guide/bring-up')
                assert json.loads(body.contents[0].text)['workflows'][0]['id'] == 'bring-up'
                result = await s.call_tool('agent_guide', {'workflow': 'add-coverage'})
                assert json.loads(result.content[0].text)['workflows'][0]['id'] == 'add-coverage'
    anyio.run(session)


def test_failure_workflow_requires_identity_and_repair_runs():
    data = guide.load()
    assert 'docs/INTEGRATION_GUIDE.md' in data['conventions']['integration_guide']
    steps = guide.select(data, 'test-fails')['workflows'][0]['steps']
    assert steps[0]['id'] == 'identity'
    fix = next(s for s in steps if s['id'] == 'fix')
    assert fix['decide'][0]['then'] == 'reproduce'
    assert any(d['then'] == 'stop' for s in steps if s['id'] == 'wave' for d in s['decide'])
