"""The agent playbook as an MCP tool and resources."""
import json

from rvw.mcp.spec import ToolSpec, schema


def _guide(workflow=None):
    from . import guide
    return guide.select(guide.load(), workflow)


def _bringup(out, timeout=1800, bring_up_only=False):
    from . import bringup
    return bringup.run_check(out, timeout=timeout, workflows=('bring-up',) if bring_up_only else ('bring-up', 'test-fails'))


def mcp_tools():
    return [ToolSpec('agent_bringup_check', 'Walk the agent guide (bring-up, then test-fails) on a scratch copy of a '
                     'tiny seeded Spinal core in a new directory; report which steps work. Native, slow (sbt, '
                     'Verilator, Spike). A setup test, not core evidence.',
                     schema({'out': {'type': 'string'}, 'timeout': {'type': 'number'},
                             'bring_up_only': {'type': 'boolean'}}, ['out']), _bringup, long=True,
                     side_effects='writes-files', native_tools=()),
            ToolSpec('agent_guide', 'Agent playbook: workflows (bring-up, a test fails, add coverage, prove a '
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
