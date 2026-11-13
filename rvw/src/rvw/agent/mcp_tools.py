"""The agent playbook as an MCP tool and resources."""
import json

from rvw.mcp.spec import ToolSpec, schema


def _guide(workflow=None):
    from . import guide
    return guide.select(guide.load(), workflow)


def mcp_tools():
    return [ToolSpec('agent_guide', 'Agent playbook: workflows (bring-up, a test fails, add coverage, prove a '
                     'property, performance question) as ordered rvw CLI and MCP calls with decision points. '
                     'Start here when you do not know which tool to call.',
                     schema({'workflow': {'type': 'string'}}), _guide, annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=())]


def mcp_resources():
    """(uri, name, description, reader) for each resource."""
    from . import guide
    data = guide.load()
    out = [('rvw://agent/guide', 'agent-guide', 'All agent workflows (rvw.agent-guide/1 JSON).',
            lambda: json.dumps(data, indent=2))]
    for w in data['workflows']:
        out.append((f'rvw://agent/guide/{w["id"]}', f'agent-guide-{w["id"]}', w['title'],
                    lambda w=w['id']: json.dumps(guide.select(data, w), indent=2)))
    return out
