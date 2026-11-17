"""Pinned workload builds and reference checks as cancellable MCP jobs."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def execute_json(action, manifest=None, recipe=None, **arguments):
    from . import core
    if manifest is not None and recipe is not None:
        raise ValueError('select either a manifest or a recipe')
    manifest = core.recipe(recipe) if recipe else manifest
    if action == 'list':
        return core.load(manifest)
    if action == 'build':
        return core.build(manifest=manifest, cc=arguments.pop('cc', 'riscv64-unknown-elf-gcc'), **arguments)
    return core.verify(**arguments)


def mcp_tools():
    select = {k: {'type': 'string'} for k in ('manifest', 'recipe')}
    result = []
    for action, properties, required in (
        ('list', select, []),
        ('build', {**select, **{k: {'type': 'string'} for k in ('source', 'out', 'cc', 'bench')}}, ['out']),
        ('verify', {**{k: {'type': 'string'} for k in ('build_path', 'out', 'oracle')},
                    'timeout': {'type': 'integer', 'minimum': 1}, 'trace': {'type': 'boolean'}}, ['build_path', 'out', 'oracle'])):
        def handler(job, _action=action, **arguments):
            return run_function(job, 'rvw.workloads.mcp_tools', 'execute_json', {'action': _action, **arguments})
        result.append(ToolSpec('workloads_' + action, 'Build or reference-check pinned open workloads. No RTL accuracy claim.',
                               schema(properties, required), handler, long=True, side_effects={'workloads_list': 'read-only; long-running', 'workloads_build': 'long-running; launches compiler; writes workload build under out', 'workloads_verify': 'long-running; launches selected reference; writes reports under out'}['workloads_' + action], native_tools={'workloads_list': (), 'workloads_build': ('RISC-V GCC',), 'workloads_verify': ('Spike', 'QEMU')}['workloads_' + action]))
    return result
