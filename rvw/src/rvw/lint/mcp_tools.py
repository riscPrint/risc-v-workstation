"""Shared lint report as a cancellable MCP job."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def _lint(settings, job, sarif=None):
    return run_function(job, 'rvw.lint.cli', 'report_outputs', {'path': settings, 'sarif_path': sarif})


def _emit(settings, out, job, sarif=None):
    return run_function(job, 'rvw.lint.cli', 'report_outputs',
                        {'path': settings, 'emit_dir': out, 'sarif_path': sarif})


def mcp_tools():
    s = {'type': 'string'}
    return [ToolSpec('lint_report', 'Run native lint, design-database lint rules, structural CDC/RDC and SDC intent. '
                     'Retain waivers and unrun checks. Optional SARIF path. No signoff.',
                     schema({'settings': s, 'sarif': {**s, 'description': 'also write SARIF 2.1.0 here'}},
                            ['settings']), _lint, long=True, annotations={'readOnlyHint': False}),
            ToolSpec('lint_emit', 'Run lint and write CDC protocol assertions (checker modules, bind lines, '
                     'checked RTL copies), the obligation list and generated SDC to a new directory. '
                     'Emitted checks are obligations, not results.',
                     schema({'settings': s, 'out': {**s, 'description': 'new or empty output directory'},
                             'sarif': s}, ['settings', 'out']), _emit, long=True)]
