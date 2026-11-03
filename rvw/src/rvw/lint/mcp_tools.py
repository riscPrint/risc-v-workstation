"""Shared lint report as a cancellable MCP job."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def _lint(settings, job):
    return run_function(job, 'rvw.lint.cli', 'report', {'path': settings})


def mcp_tools():
    return [ToolSpec('lint_report', 'Run native lint and structural CDC/RDC. Retain waivers and unrun checks. No signoff.',
                     schema({'settings': {'type': 'string'}}, ['settings']), _lint,
                     long=True, annotations={'readOnlyHint': True})]
