#!/usr/bin/env python3
"""Build pinned optional engines outside the workstation checkout."""
import argparse
import os
from pathlib import Path
import shlex
import sys
import subprocess

RIC3_REV = '02c12ff1407b3474b7eb85c4531a06ad2eb86933'
EBMC_REV = '2f4f2fc76f450557de3eef5f3e3d075869999e85'
NIGHTLY = 'nightly-2025-11-20'


def install(engine, prefix, dry=False):
    prefix = Path(prefix).expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if prefix == repo or repo in prefix.parents:
        raise ValueError('formal engine builds must be outside the repository')
    def run(*cmd, **kw):
        print(shlex.join(map(str, cmd)), flush=True)
        if not dry:
            subprocess.run(list(map(str, cmd)), check=True, **kw)
    run('mkdir', '-p', prefix)
    if engine == 'ric3':
        run('rustup', 'toolchain', 'install', NIGHTLY, '--profile', 'minimal')
        if dry:
            rustc = '<pinned-nightly-rustc>'
        else:
            rustc = subprocess.check_output(['rustup', 'which', '--toolchain', NIGHTLY, 'rustc'], text=True).strip()
        env = {**os.environ, 'RUSTC': rustc, 'CARGO_TARGET_DIR': str(prefix / 'ric3-target')}
        if sys.platform == 'darwin':
            brew = '/opt/homebrew' if dry else subprocess.check_output(['brew', '--prefix'], text=True).strip()
            env['LIBRARY_PATH'] = brew + '/lib' + (':' + env['LIBRARY_PATH'] if env.get('LIBRARY_PATH') else '')
        run('nice', '-n', '10', 'rustup', 'run', NIGHTLY, 'cargo', 'install', '--git',
            'https://github.com/gipsyh/rIC3', '--rev', RIC3_REV, '--locked', '--root', prefix,
            '-j', '2', env=env)
    else:
        src = prefix / 'hw-cbmc'
        if not src.exists():
            run('git', 'clone', '--no-checkout', 'https://github.com/diffblue/hw-cbmc.git', src)
        run('git', '-C', src, 'fetch', 'origin', EBMC_REV)
        run('git', '-C', src, 'checkout', '--detach', EBMC_REV)
        run('git', '-C', src, 'submodule', 'update', '--init', '--recursive', '--depth', '1')
        run('nice', '-n', '10', 'make', '-C', src / 'lib/cbmc/src', 'minisat2-download')
        run('nice', '-n', '10', 'make', '-C', src / 'src', '-j2')
        run('mkdir', '-p', prefix / 'bin')
        run('cp', src / 'src/ebmc/ebmc', prefix / 'bin/ebmc')
    return prefix / 'bin'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('engine', choices=['ric3', 'ebmc'])
    p.add_argument('--prefix', default='~/.cache/rvw/formal-engines')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    print(install(a.engine, a.prefix, a.dry_run))
