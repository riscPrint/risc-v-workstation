"""Protocol agent discovery and bench generation."""
from rvw.mcp.spec import ToolSpec,schema


def mcp_tools():
    string={'type':'string'}
    return [ToolSpec('vip_list','List protocol agents and exact Spinal bus classes.',schema({}),agents,
                     annotations={'readOnlyHint':True}, side_effects='read-only', native_tools=()),
            ToolSpec('vip_buses','List supported typed buses from SpinalDB.',schema({'db':string,'port_map':string},['db']),buses,
                     annotations={'readOnlyHint':True}, side_effects='read-only', native_tools=()),
            ToolSpec('vip_bench','Generate a bound cocotb skeleton. It requires project stimulus and expectations.',
                     schema({k:string for k in ('db','out','bus','clock','reset','port_map')},['db','out']),skeleton, side_effects='writes a new bench file at out', native_tools=())]


def agents():
    """Load the handler on first use."""
    from rvw.vip.catalog import agents as implementation
    return implementation()

def buses(db, port_map=None):
    """Load the handler on first use."""
    from rvw.vip.catalog import buses as implementation
    return implementation(db, port_map)

def skeleton(db, out, bus=None, clock='clk', reset='reset_n', port_map=None):
    """Load the handler on first use."""
    from rvw.vip.catalog import skeleton as implementation
    return implementation(db, out, bus, clock, reset, port_map)
