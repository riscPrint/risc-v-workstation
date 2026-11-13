"""Project scaffold calls. Generation does not build or qualify a core."""
from rvw.mcp.spec import ToolSpec, schema


def _scaffold(out, isa, **options):
    from .scaffold import scaffold
    from .mapped import mapped_scaffold
    if options.get('spinal_top') or options.get('verilog_top'):
        options['top'] = options.pop('spinal_top', None)
        # Mapped builds always wire the adapter dependencies.
        options.pop('wire_build', None)
        return mapped_scaffold(out, isa=isa, **options)
    defaults = dict(wire_build=False, dry_run=False, sbt_project=None, name=None)
    defaults.update(options)
    return scaffold(out, isa=isa, **defaults)


def mcp_tools():
    string = {'type': 'string'}
    boolean = {'type': 'boolean', 'default': False}
    array = {'type': 'array', 'items': string}
    fields = {key: string for key in (
        'out', 'isa', 'name', 'sbt_project', 'spinal_top', 'verilog_top',
        'clock', 'reset', 'rvfi_prefix', 'reset_pc', 'ram', 'yosys')}
    fields.update({key: boolean for key in (
        'wire_build', 'dry_run', 'force', 'accept_platform_defaults')})
    fields.update({key: array for key in (
        'verilog', 'defines', 'params', 'buses', 'irq', 'constants')})
    fields['reset_active'] = {'type': 'string', 'enum': ['high', 'low']}
    return [ToolSpec('init_scaffold',
                     'Plan or write core project files. For a mapped adapter, supply spinal_top or '
                     'verilog_top, reset_pc and buses. Each bus is NAME:PROTOCOL:key=port,...; '
                     'req-rsp roles: cmd_valid,address,rsp_valid,rdata; optional '
                     'cmd_ready,write,wdata,mask,error,rsp_ready,write_response=1. '
                     'Generation does not build or qualify the core.',
                     schema(fields, ['out', 'isa']), _scaffold,
                     side_effects='writes project files under out unless dry_run is true', native_tools=())]
