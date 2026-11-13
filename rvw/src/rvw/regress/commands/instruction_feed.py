"""Offline instruction source for the generic C1 fetch injection port."""
import json


def run(args):
    try:result=generate(args.elf,args.out,args.word_bytes)
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'error','message':str(exc)}));return 2
    print(json.dumps(result,indent=2));return 0


def register(sub):
    p=sub.add_parser('instruction-feed',help='build a fetch-port word feed from a reference ELF; no execution credit')
    p.add_argument('--elf',required=True);p.add_argument('--out',required=True)
    p.add_argument('--word-bytes',type=int,choices=[4,8],default=4);p.add_argument('--json',action='store_true')
    p.set_defaults(func=run)


def mcp_tools():
    from rvw.mcp.spec import ToolSpec,schema
    return [ToolSpec('regress_instruction_feed','Build an offline reference-image word source for the C1 instruction port.',
        schema({'elf':{'type':'string'},'out':{'type':'string'},'word_bytes':{'type':'integer','enum':[4,8]}},['elf','out']),
        generate,isolate=True,side_effects='writes-files',native_tools=())]


def generate(elf, out, word_bytes=4):
    """Load the handler on first use."""
    from rvw.regress.instruction_feed import generate as implementation
    return implementation(elf, out, word_bytes)
