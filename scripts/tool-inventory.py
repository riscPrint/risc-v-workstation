#!/usr/bin/env python3
"""Read the packaged inventory without importing optional rvw dependencies."""
import argparse
import importlib.util
from pathlib import Path
import platform
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inventory', ROOT / 'rvw/src/rvw/doctor/inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expand', nargs=argparse.REMAINDER)
    parser.add_argument('--extra', nargs='*')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    data = inventory.load()
    if args.expand is not None:
        original = iter(args.expand)
        for flag in original:
            if flag == '--profile':
                profile = next(original, '')
                try:
                    print('\n'.join(inventory.flags(profile)))
                except ValueError as exc:
                    parser.error(str(exc))
            elif flag == '--all':
                print('\n'.join(inventory.flags('all')))
            else:
                print(flag)
        return 0
    if args.extra is None:
        parser.error('use --expand or --extra')
    records = {r['name']: r for r in inventory.report()}
    failed = False
    python_extras = sorted({'cocotb': 'cocotb', 'pyuvm': 'pyuvm', 'wellen': 'waves'}[f] for f in args.extra if f in ('cocotb', 'pyuvm', 'wellen'))
    synced = False
    for flag in args.extra:
        tools = [t for t in data['tools'] if t['flag'] == flag and not t['legacy']]
        if not tools:
            parser.error('unknown optional tool flag: --with-' + flag)
        for tool in tools:
            record = records[tool['name']]
            if args.check:
                print(record['status'].upper(), tool['name'], record['install_command'])
                failed |= record['status'] != 'installed'
                continue
            extra = {'cocotb': 'cocotb', 'pyuvm': 'pyuvm', 'wellen': 'waves'}.get(flag)
            if extra:
                if synced:
                    continue
                synced = True
                cmd = ['uv', 'sync', '--locked', '--extra', 'mcp', *[arg for value in python_extras for arg in ('--extra', value)], '--project', str(ROOT / 'rvw')]
            else:
                recipe = tool['install']['macos' if platform.system() == 'Darwin' else 'apt']
                print(tool['name'] + ': ' + (recipe or tool['install']['source']))
                if not args.dry_run:
                    # Package approval remains with install.sh. Do not run arbitrary recipes.
                    print('Manual setup required. See inventory install recipe above.')
                    failed = True
                continue
            print(shlex.join(cmd))
            if not args.dry_run:
                subprocess.run(cmd, check=True)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
