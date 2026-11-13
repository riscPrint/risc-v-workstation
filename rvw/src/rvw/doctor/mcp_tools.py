from rvw.mcp.spec import ToolSpec, schema
from .check import diagnose
from .inventory import load


def mcp_tools():
    return [ToolSpec('rvw_doctor', 'Read-only setup checks. No native build/run conformance claim. Installation is CLI-only.',
                     schema({'project': {'type': 'string'}, 'features': {'type': 'string', 'default': 'sim,riscv-gcc'}}),
                     diagnose, isolate=True, annotations={'readOnlyHint': True}, side_effects='read-only; launches native tools for version probes and project adapter info', native_tools=tuple(t['name'] for t in load()['tools'])),
            ToolSpec('doctor_smoke', 'Build and run an explicit ELF through the selected project adapter. '
                     'Write C1 smoke evidence. Optional Spike checks need a reviewed platform. This is a native job.',
                     schema({'elf': {'type': 'string'}, 'project': {'type': 'string'},
                             'options': {'type': 'string', 'default': 'rvfi'}, 'platform': {'type': 'string'},
                             'conformance': {'type': 'boolean', 'default': False}}, ['elf']),
                     _smoke, long=True, side_effects='long-running; launches configured native project adapter and optional Spike; writes smoke evidence under project out',
                     native_tools=('Spike',))]


def _smoke(elf, project=None, options='rvfi', platform=None, conformance=False):
    return diagnose(project=project, features='sim,riscv-gcc,cosim', smoke_elf=elf,
                    smoke_flags=options, smoke_platform=platform, conformance=conformance)
