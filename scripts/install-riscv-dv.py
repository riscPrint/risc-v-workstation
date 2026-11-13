#!/usr/bin/env python3
"""Install pinned pygen outside the workstation checkout."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

REVISION = 'f557b89ed6881a20515481a2585e9d004cd9642b'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    destination = Path(os.environ.get('RVW_RISCV_DV', Path.home()/'.cache/rvw/riscv-dv')).resolve()
    root = Path(__file__).resolve().parents[1]
    if destination == root or root in destination.parents:
        raise ValueError('RVW_RISCV_DV must be outside the repository')
    def run(*argv):
        print(' '.join(map(str, argv)))
        if not args.dry_run:
            subprocess.run(list(map(str, argv)), check=True, timeout=300)
    if not args.check:
        if not destination.exists():
            run('git', 'clone', 'https://github.com/chipsalliance/riscv-dv.git', destination)
            run('git', '-C', destination, 'checkout', '--detach', REVISION)
        # Never move or clean an existing external checkout.
    if not args.dry_run:
        actual = subprocess.check_output(['git', '-C', str(destination), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(destination), 'status', '--porcelain', '--untracked-files=no'], text=True)
        if actual != REVISION or dirty:
            raise ValueError('riscv-dv must be clean at '+REVISION)
    python = destination.parent/'riscv-dv-venv/bin/python'
    if not args.check:
        run('uv', 'venv', '--python', '3.11', '--allow-existing', python.parent.parent)
        run('uv', 'pip', 'install', '--python', python, 'pyboolector==3.2.4.38488416565',
            'pyvsc==0.9.1.10086043874', 'pip', 'PyYAML', 'bitstring', 'tabulate', 'pandas==2.2.3')
    run(python, '-c', 'from importlib.metadata import version; '
        'assert version("pyvsc") == "0.9.1.10086043874"; '
        'assert version("pyboolector") == "3.2.4.38488416565"; '
        'import vsc, pyboolector, pandas, yaml, bitstring, tabulate')
    print('RISCV-DV '+REVISION+' at '+str(destination))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
