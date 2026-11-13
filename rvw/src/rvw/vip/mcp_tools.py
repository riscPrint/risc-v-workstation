"""Protocol agent discovery and bench generation."""
from rvw.mcp.spec import ToolSpec,schema
from .catalog import agents,buses,skeleton


def mcp_tools():
    string={'type':'string'}
    return [ToolSpec('vip_list','List protocol agents and exact Spinal bus classes.',schema({}),agents,
                     annotations={'readOnlyHint':True}, side_effects='read-only', native_tools=()),
            ToolSpec('vip_buses','List supported typed buses from SpinalDB.',schema({'db':string,'port_map':string},['db']),buses,
                     annotations={'readOnlyHint':True}, side_effects='read-only', native_tools=()),
            ToolSpec('vip_bench','Generate a bound cocotb skeleton. It requires project stimulus and expectations.',
                     schema({k:string for k in ('db','out','bus','clock','reset','port_map')},['db','out']),skeleton, side_effects='writes a new bench file at out', native_tools=())]
