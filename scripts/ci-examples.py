#!/usr/bin/env python3
"""Run pinned Vex smoke suites in private copies of cached core checkouts."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CORES = {
    'vexriscv': ('VexRiscv', 'baf7dc82f855eddaf5b0a20a6802c526f127e38a', 'VEXRISCV'),
    'vexiiriscv': ('VexiiRiscv', '9f70315deb3390b283995c5b8f1bd38215ecf52b', 'VEXIIRISCV'),
}


def run(argv, cwd, env):
    subprocess.run(argv, cwd=cwd, env=env, check=True, timeout=1700)


def main():
    cache = Path(os.environ.get('RVW_CI_CORE_CACHE', Path.home() / '.cache/rvw-ci/cores'))
    cache.mkdir(parents=True, exist_ok=True)
    for name, (repo, revision, selector) in CORES.items():
        mirror = cache / (repo + '.git')
        env = {**os.environ, 'RVW_HOME': str(ROOT), 'RVW_PYTHON': sys.executable}
        if not mirror.exists():
            run(['git', 'clone', '--mirror', 'https://github.com/SpinalHDL/' + repo, str(mirror)], ROOT, env)
        with tempfile.TemporaryDirectory(prefix='rvw-ci-core-') as directory:
            core = Path(directory) / repo
            run(['git', 'clone', '--no-checkout', str(mirror), str(core)], ROOT, env)
            run(['git', 'remote', 'set-url', 'origin', 'https://github.com/SpinalHDL/' + repo], core, env)
            run(['git', 'checkout', '--detach', revision], core, env)
            if name == 'vexiiriscv':
                run(['git', 'submodule', 'update', '--init', 'ext/SpinalHDL', 'ext/rvls'], core, env)
            env[selector] = str(core)
            example = ROOT / 'examples' / name
            # Copy only tracked project files; never reuse local build output.
            names = subprocess.check_output(['git', 'ls-files', '-z', str(example.relative_to(ROOT))], cwd=ROOT).decode().split('\0')
            for entry in filter(None, names):
                source = ROOT / entry
                target = core / source.relative_to(example)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            out = core / 'rvw/out/programs'
            out.mkdir(parents=True, exist_ok=True)
            for program in ('smoke', 'trap'):
                run(['riscv64-unknown-elf-gcc', '-march=rv32im_zicsr_zifencei', '-mabi=ilp32', '-nostdlib', '-nostartfiles', '-T', 'rvw/programs/link.ld', '-Wl,--build-id=none', f'rvw/programs/{program}.S', '-o', str(out / program)], core, env)
            # Private output needs no shared core lock.
            env['RVW_VEX_LOCK'] = 'ci-examples-' + name
            run([sys.executable, '-m', 'rvw', '--project', str(core / 'rvw.toml'), 'regress', 'run', '--suite', 'smoke'], core, env)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
