"""Project scaffold calls. Generation does not build or qualify a core."""
from rvw.mcp.spec import ToolSpec, schema


def _scaffold(out, isa, wire_build=False, dry_run=False, sbt_project=None, name=None):
    from .scaffold import scaffold
    return scaffold(out, isa=isa, wire_build=wire_build, dry_run=dry_run,
                    sbt_project=sbt_project, name=name)


def mcp_tools():
    string = {'type': 'string'}
    return [ToolSpec('init_scaffold', 'Plan or write rvw project files in an existing Spinal/sbt core repository. '
                     'Refuse existing output files. Generation is not a build or a core qualification.',
                     schema({'out': string, 'isa': string, 'name': string, 'sbt_project': string,
                             'wire_build': {'type': 'boolean', 'default': False},
                             'dry_run': {'type': 'boolean', 'default': False}}, ['out', 'isa']),
                     _scaffold, side_effects='writes project files under out unless dry_run is true', native_tools=())]
