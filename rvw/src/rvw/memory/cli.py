"""Memory ordering inputs and observation checks."""
import json
from pathlib import Path
from .multihart import images, check


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
    return {'mismatch': 1, 'inconclusive': 3}.get(result.get('status'), 0)
