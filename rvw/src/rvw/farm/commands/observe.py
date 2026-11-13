"""Native waveform observations for advisory impact selection."""
import json
from pathlib import Path
from rvw.mcp.spec import ToolSpec, schema


def execute(db, root, wave_prefix, out=None):
    from rvw.farm.observations import observe
    from rvw.results import write_json
    report = observe(db, root, wave_prefix)
    if out:
        write_json(out, report)
    return report


def register(sub):
    parser = sub.add_parser('observe', help=__doc__)
    for name in ('db','root','wave-prefix','out'):
        parser.add_argument('--'+name, required=True)
    parser.set_defaults(func=run)


def run(args):
    print(json.dumps(execute(args.db,args.root,args.wave_prefix,args.out)))


def mcp_tools():
    string={'type':'string'}
    return [ToolSpec('farm_observe',__doc__,schema({k:string for k in ('db','root','wave_prefix','out')},
        ['db','root','wave_prefix']),execute,long=True,
        side_effects='writes optional observation catalogue under out; reads C1 waveform and design database; may launch captured FST conversion',native_tools=('GTKWave tools',))]
