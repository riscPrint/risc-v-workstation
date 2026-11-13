"""Portable deterministic replay commands."""
import json
from pathlib import Path
from .portable import pack, replay


def register(sub):
    save = sub.add_parser('replay-pack', help='pack a failing run, sources and trace checkpoint into one offline archive')
    save.add_argument('run_dir', type=Path)
    save.add_argument('--recipe', type=Path, required=True)
    save.add_argument('--out', type=Path, required=True)
    save.add_argument('--checkpoint-cycle', type=int)
    save.set_defaults(func=save_command)
    run = sub.add_parser('replay', help='rebuild pinned source snapshots and verify an archived failing run')
    run.add_argument('archive', type=Path)
    run.add_argument('--out', type=Path, required=True)
    run.add_argument('--timeout', type=float, default=600)
    run.add_argument('--lock')
    run.set_defaults(func=run_command)


def save_command(args):
    return _print(lambda: pack(args.run_dir, args.recipe, args.out, checkpoint_cycle=args.checkpoint_cycle))


def run_command(args):
    return _print(lambda: replay(args.archive, args.out, timeout=args.timeout, lock=args.lock))


def _print(action):
    try:
        result = action()
        print(json.dumps(result))
        return 0 if result.get('status') != 'mismatch' else 1
    except (OSError, ValueError, KeyError) as error:
        print(json.dumps({'status': 'error', 'message': str(error)}))
        return 2
