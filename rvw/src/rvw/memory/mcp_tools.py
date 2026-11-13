from rvw.mcp.spec import ToolSpec, schema
from .multihart import check, images
from .axiomatic import check as axiomatic_check
from .concurrent import generate


def mcp_tools():
    return [ToolSpec('memory_axiomatic', 'Search scalar RVWMO/Ztso execution graphs with complete dependency observations.',
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
