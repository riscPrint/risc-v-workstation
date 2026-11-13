"""Read project-owned verification-plan evidence."""
from rvw.mcp.spec import ToolSpec,schema
from rvw.mcp.worker import handler


def mcp_tools():
    s={'type':'string'}
    return [ToolSpec('plan_status','Roll up project requirements and feature evidence. Report coverage holes, test/formal/check gaps and compatible trends. Recorded closure grants no C4 accept.',
                    schema({'plan':s,'previous':s,'out':s},['plan']),
                    handler('rvw.plan.cli','status'),long=True,annotations={'readOnlyHint':True})]
