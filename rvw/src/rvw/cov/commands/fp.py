"""Scalar FP operand, rounding-mode and raised-flag cross coverage."""
import json
from pathlib import Path


def register(sub):
    p=sub.add_parser('fp',help='merge scalar FP class and raised-flag crosses from C1-bound C2/2')
    p.add_argument('traces',nargs='+')
    p.add_argument('--width',type=int,choices=(32,64),required=True)
    p.add_argument('--out',type=Path)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def execute_json(traces, width, out=None):
    from rvw.cov.fp import report_traces
    if out is not None and any(Path(out).resolve()==Path(trace).resolve() for trace in traces):
        raise ValueError('coverage output must not overwrite an input trace')
    result=report_traces(traces,width)
    if out is not None:
        Path(out).write_text(json.dumps(result,indent=2)+'\n')
    return result


def run(args):
    try:
        result=execute_json(args.traces,args.width,args.out)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'error','message':str(exc)}))
        return 2
    if args.json:print(json.dumps(result,indent=2))
    else:print(f"FP{args.width}: {result['hit_bins']}/{result['bins']} flag crosses; "
               f"{result['hit_operand_class_bins']}/{result['operand_class_bins']} class bins")
    return 0


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('cov_fp','Report scalar F/D/C class, rounding-mode and raised-flag crosses. Requires complete C1-bound passing DUT C2/2 traces.',
        schema({'traces':{'type':'array','items':{'type':'string'}},
                'width':{'type':'integer','enum':[32,64]},'out':{'type':'string'}},['traces','width']),
        execute_json,isolate=True,side_effects='writes-files if out is given; read-only otherwise',native_tools=())]
