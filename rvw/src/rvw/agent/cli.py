"""`rvw agent guide`: print the agent playbook."""
import json
from pathlib import Path


def register(subparsers):
    p = subparsers.add_parser('agent', help='Agent playbook and helpers')
    sub = p.add_subparsers(dest='action', required=True)
    g = sub.add_parser('guide', help='workflows as ordered rvw/MCP calls with decision points')
    g.add_argument('--workflow', help='one workflow id (default: all)')
    g.add_argument('--json', action='store_true', help='rvw.agent-guide/1 JSON (default: text)')
    g.add_argument('--markdown', action='store_true', help='the generated docs/AGENT_SETUP.md block')
    g.add_argument('--write', type=Path, help='with --markdown: replace the block in this file')
    g.set_defaults(func=_guide)


def _guide(args):
    from . import guide
    data = guide.select(guide.load(), args.workflow)
    if args.markdown:
        block = guide.markdown(data)
        if args.write:
            args.write.write_text(guide.embed(args.write.read_text(), block))
        else:
            print(block, end='')
    elif args.json:
        print(json.dumps(data, indent=2))
    else:
        for w in data['workflows']:
            print(f'{w["id"]}: {w["title"]}')
            for s in w['steps']:
                print(f'  {s["id"]}: rvw {" ".join(s["cli"])}' if s.get('cli') else f'  {s["id"]}: (manual) {s["do"]}')
    return 0
