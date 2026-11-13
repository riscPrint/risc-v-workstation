"""Memory ordering inputs and observation checks."""
import json
from pathlib import Path
from .multihart import images, check
from .axiomatic import check as axiomatic_check
from .concurrent import generate


def register(sub):
    p = sub.add_parser('memory', help=__doc__)
    commands = p.add_subparsers(required=True)
    image = commands.add_parser('images', help='prepare pinned per-hart ELF inputs for a project adapter')
    image.add_argument('--hart-image', action='append', required=True, metavar='HART=ELF')
    image.set_defaults(func=command_images)
    c = commands.add_parser('check', help='check a C2/2 serialized boundary against independent bytes')
    c.add_argument('--trace', required=True, type=Path)
    c.add_argument('--reference', required=True, type=Path)
    c.set_defaults(func=command_check)
    a = commands.add_parser('axiomatic', help='search scalar RVWMO/Ztso candidate execution graphs')
    a.add_argument('--trace', required=True, type=Path)
    a.add_argument('--reference', required=True, type=Path)
    a.add_argument('--model', choices=('rvwmo', 'ztso'), default='rvwmo')
    a.add_argument('--limit', type=int, default=100000)
    a.set_defaults(func=lambda args: emit(lambda: axiomatic_check(args.trace, args.reference, args.model, args.limit)))
    g = commands.add_parser('generate', help='generate seeded RV64 concurrent program fragments')
    g.add_argument('--seed', type=int, default=1)
    g.add_argument('--harts', type=int, default=2)
    g.add_argument('--length', type=int, default=16)
    g.set_defaults(func=lambda args: emit(lambda: generate(args.seed, args.harts, args.length)))


def command_images(args):
    return emit(lambda: images(args.hart_image))


def command_check(args):
    return emit(lambda: check(args.trace, args.reference))


def emit(call):
    try:
        result = call()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {'status': 'inconclusive', 'reason': str(exc)}
    print(json.dumps(result, indent=2))
    return {'mismatch': 1, 'forbidden': 1, 'inconclusive': 3}.get(result.get('status'), 0)
