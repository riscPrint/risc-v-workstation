"""Source navigation report for code and functional coverage."""
import json
from rvw.cov.source_report import source_report


def run(args):
    try:
        result = source_report(args.database,args.functional,args.bindings)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'error','message':str(exc)}))
        return 2
    print(json.dumps(result,indent=2))
    return 0


def register(sub):
    p=sub.add_parser('source-report',help='join native and declared functional goals per source line')
    for key in ('database','functional','bindings'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('cov_source_report','Join native counters and project-declared functional source links.',
        schema({k:{'type':'string'} for k in ('database','functional','bindings')},
               ['database','functional','bindings']), source_report, isolate=True, side_effects='read-only', native_tools=())]
