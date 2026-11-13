from rvw.mcp.spec import ToolSpec,schema
from .model import generate,check_vectors


def mcp_tools():
    string = {'type':'string'}
    return [
        ToolSpec('verification_plan_generate','Generate unrun extension and envcfg cases from explicit versioned obligations.',schema({'declaration':string,'out':string},['declaration','out']),generate,isolate=True, side_effects='writes a new plan file at out', native_tools=()),
        ToolSpec('verification_plan_check','Compare supplied observations with separately authored reference vectors as bounded C3 evidence.',schema({'plan':string,'observations':string,'out':string},['plan','observations','out']),check_vectors,isolate=True, side_effects='writes a new results file at out', native_tools=()),
    ]
