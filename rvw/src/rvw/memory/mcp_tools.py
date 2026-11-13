from rvw.mcp.spec import ToolSpec, schema
from .multihart import check, images


def mcp_tools():
    return [ToolSpec('memory_images', 'Prepare pinned per-hart ELF inputs. Does not run a DUT.',
                     schema({'hart_images': {'type': 'array', 'items': {'type': 'string'}}}, required=['hart_images']), images),
            ToolSpec('memory_check', 'Check C2/2 serialized memory against independent stimulus bytes. No RVWMO proof.',
                     schema({'trace': {'type': 'string'}, 'reference': {'type': 'string'}}, required=['trace', 'reference']), check)]
