from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def handler(job, **kw):
    return run_function(job, 'rvw.sample.flow', 'run', kw)


def mcp_tools():
    return [ToolSpec('sample_run', 'Profile Spike, cluster BBVs, transfer checkpoints to RTL and estimate IPC. Failed equality checks exclude points. Resume uses the same output directory.',
        schema(dict(manifest={'type':'string'}, out={'type':'string'},
                    interval={'type':'integer','minimum':2}, max_k={'type':'integer','minimum':1},
                    warmup={'type':'integer','minimum':0}, seed={'type':'integer'}), ['manifest','out']),
        handler, long=True, side_effects='launches serial Spike and project RTL jobs; writes under out',
        native_tools=('Spike',))]
