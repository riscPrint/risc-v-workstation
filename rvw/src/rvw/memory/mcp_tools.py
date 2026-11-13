from rvw.mcp.spec import ToolSpec, schema
from .multihart import check, images
from .axiomatic import check as axiomatic_check
from .concurrent import generate
from .tilelink_bind import generate as tilelink_bind
from .directory_model import check as directory_check


def mcp_tools():
    return [ToolSpec('memory_directory', 'Check a finite queued MESI/MOESI directory model with named weak fairness.',
                     schema({'profile': {'type': 'string', 'default': 'mesi'}, 'lines': {'type': 'integer', 'default': 1},
                             'requests': {'type': 'integer', 'default': 1}, 'limit': {'type': 'integer', 'default': 100000},
                             'bug': {'type': 'string'} }), directory_check),
            ToolSpec('memory_tilelink_bind', 'Generate a bounded two-client single-beat TL-C monitor and bind from SpinalDB.',
                     schema({'database': {'type': 'string'}, 'profile': {'type': 'string'}, 'out': {'type': 'string'}},
                            required=['database', 'profile', 'out']), tilelink_bind),
            ToolSpec('memory_axiomatic', 'Search scalar RVWMO/Ztso execution graphs with complete dependency observations.',
                     schema({'trace': {'type': 'string'}, 'reference': {'type': 'string'},
                             'model': {'type': 'string', 'default': 'rvwmo'}, 'limit': {'type': 'integer', 'default': 100000}},
                            required=['trace', 'reference']), axiomatic_check),
            ToolSpec('memory_generate', 'Generate seeded concurrent RV64 fragments. Does not execute them.',
                     schema({'seed': {'type': 'integer', 'default': 1}, 'harts': {'type': 'integer', 'default': 2},
                             'length': {'type': 'integer', 'default': 16}}), generate),
            ToolSpec('memory_images', 'Prepare pinned per-hart ELF inputs. Does not run a DUT.',
                     schema({'hart_images': {'type': 'array', 'items': {'type': 'string'}}}, required=['hart_images']), images),
            ToolSpec('memory_check', 'Check C2/2 serialized memory against independent stimulus bytes. No RVWMO proof.',
                     schema({'trace': {'type': 'string'}, 'reference': {'type': 'string'}}, required=['trace', 'reference']), check)]
