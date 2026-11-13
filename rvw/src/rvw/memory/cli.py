"""Memory ordering inputs and observation checks."""
import json
from pathlib import Path
from .multihart import images, check
from .dependency_consistency import DeclarationError
from .axiomatic import check as axiomatic_check
from .concurrent import generate
from .tilelink_bind import generate as tilelink_bind
from .directory_model import check as directory_check
from .concurrent_native import smoke as concurrent_smoke


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
    t = commands.add_parser('tilelink-bind', help='generate a bounded TL-C complete-message monitor and bind')
    t.add_argument('--database', required=True, type=Path)
    t.add_argument('--profile', required=True, type=Path)
    t.add_argument('--out', required=True, type=Path)
    t.set_defaults(func=lambda args: emit(lambda: tilelink_bind(args.database, args.profile, args.out)))
    d = commands.add_parser('directory', help='check finite queued MESI/MOESI directory profiles')
    d.add_argument('--profile', choices=('mesi', 'moesi'), default='mesi')
    d.add_argument('--lines', type=int, default=1)
    d.add_argument('--requests', type=int, default=1)
    d.add_argument('--limit', type=int, default=100000)
    d.add_argument('--bug', choices=('lost_ack', 'stale_data', 'early_grant', 'starvation', 'cyclic_wait'))
    d.set_defaults(func=lambda args: emit(lambda: directory_check(args.profile, args.lines, args.requests, args.limit, args.bug)))
    n = commands.add_parser('concurrent-smoke', help='run a bounded native Spike concurrent completion smoke')
    n.add_argument('--out', required=True, type=Path)
    n.add_argument('--seed', type=int, default=1)
    n.add_argument('--harts', type=int, default=2)
    n.add_argument('--length', type=int, default=16)
    n.add_argument('--gcc', default='riscv64-unknown-elf-gcc')
    n.add_argument('--spike', default='spike')
    n.add_argument('--timeout', type=float, default=30)
    n.set_defaults(func=lambda args: emit(lambda: concurrent_smoke(args.out, args.seed, args.harts, args.length, args.gcc, args.spike, args.timeout)))
    from rvw.common.subcommands import register_commands
    register_commands("rvw.memory", commands)


def command_images(args):
    return emit(lambda: images(args.hart_image))


def command_check(args):
    return emit(lambda: check(args.trace, args.reference))


def emit(call):
    try:
        result = call()
    except DeclarationError as exc:
        result = {'status': 'error', 'reason': str(exc)}
    except (ValueError, OSError, KeyError, TypeError) as exc:
        result = {'status': 'inconclusive', 'reason': str(exc)}
    print(json.dumps(result, indent=2))
    return {'error': 2, 'mismatch': 1, 'forbidden': 1, 'fail': 1, 'inconclusive': 3}.get(result.get('status'), 0)
