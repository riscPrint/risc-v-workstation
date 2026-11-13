from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def handler(job, **kw):
    return run_function(job, 'rvw.sample.flow', 'run', kw)


def validation_handler(job, **kw):
    return run_function(job, 'rvw.sample.validation', 'validate', kw)

def warming_handler(job, **kw):
    return run_function(job, 'rvw.sample.warming', 'sweep', kw)

def mcp_tools():
    return [ToolSpec('sample_run', 'Profile Spike, cluster BBVs, transfer checkpoints to RTL and estimate IPC. Failed equality checks exclude points. Resume uses the same output directory.',
        schema(dict(manifest={'type':'string'}, out={'type':'string'},
                    validation_report={'type':'string'}, interval={'type':'integer','minimum':2}, max_k={'type':'integer','minimum':1},
                    warmup={'type':'integer','minimum':0}, seed={'type':'integer'}), ['manifest','out']),
        handler, long=True, side_effects='launches serial Spike and project RTL jobs; writes under out',
        native_tools=('Spike',)),
        ToolSpec('sample_validate', 'Compare full RTL IPC with sampled IPC for interval and cluster settings. Report empirical error, not statistical confidence.',
            schema(dict(manifest={'type':'string'},out={'type':'string'},
                        intervals={'type':'array','items':{'type':'integer','minimum':2}},
                        clusters={'type':'array','items':{'type':'integer','minimum':1}},
                        warmup={'type':'integer','minimum':0}), ['manifest','out']),
            validation_handler,long=True,side_effects='launches serial full and sampled RTL jobs; writes under out',native_tools=('Spike',)),
        ToolSpec('sample_warmup', 'Measure detailed RTL warm-up bias at one fixed instruction ROI against a full reset prefix. No functional injection is claimed.',
            schema(dict(manifest={'type':'string'},out={'type':'string'},start={'type':'integer','minimum':1},
                        length={'type':'integer','minimum':2},lengths={'type':'array','items':{'type':'integer','minimum':0}},
                        target_percent={'type':'number','minimum':0}), ['manifest','out','start','length']),
            warming_handler,long=True,side_effects='launches serial baseline and warm-up RTL jobs; writes under out',native_tools=('Spike',))]
