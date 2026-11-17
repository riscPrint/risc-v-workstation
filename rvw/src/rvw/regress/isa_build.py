"""Out-of-tree riscv-tests ISA builds with captured source and ELF identities."""
import hashlib
import json
from pathlib import Path
import re
import shutil

from rvw.common.dependencies import resolve
from rvw.common.proc import run_group
from rvw.regress.source import describe


def is_elf(path):
    if not path.is_file():
        return False
    with path.open("rb") as stream:
        return stream.read(4) == b"\x7fELF"


def build(out, xlen=64, source=None, targets=None, environments='p,v',
          compiler_prefix='riscv64-unknown-elf-', timeout=300, jobs=2, elf_dir=None):
    if xlen not in (32, 64) or not 1 <= jobs <= 8 or timeout <= 0:
        raise ValueError('invalid XLEN, jobs or timeout')
    source = Path(source or resolve('riscv-tests', acquire=True)['path']).resolve()
    identity = describe(source)
    if not identity.rev or identity.dirty or not identity.reusable:
        raise ValueError('riscv-tests source must be a clean identifiable Git checkout')
    if not (source / 'env/p/riscv_test.h').is_file():
        raise ValueError('riscv-tests env submodule is missing')
    envs = environments.split(',')
    if not envs or set(envs) - {'p', 'v'}:
        raise ValueError('environments must select p or v')
    if targets:
        selected = targets.split(',') if isinstance(targets, str) else list(targets)
        if not selected or any(not re.fullmatch(rf'rv{xlen}[a-z0-9]+-[pv]-[a-zA-Z0-9_]+', t) for t in selected):
            raise ValueError('invalid ISA targets')
    else:
        # Ask upstream Make for its standard ISA selection; do not invent an ISA list.
        selected = ['all']
    compiler = shutil.which(compiler_prefix + 'gcc')
    if not compiler:
        raise ValueError('RISC-V compiler not found: ' + compiler_prefix + 'gcc')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    isa = Path(elf_dir).resolve() if elf_dir else out / 'isa'
    if isa == source or source in isa.parents:
        raise ValueError('ELF output must be outside the source checkout')
    isa.mkdir(parents=True, exist_ok=False)
    command = ['make', f'-j{jobs}', '-f', str(source / 'isa/Makefile'),
               'src_dir=' + str(source / 'isa'), f'XLEN={xlen}',
               'RISCV_PREFIX=' + compiler_prefix, *selected]
    # Upstream all includes both p and v. Explicit env filtering uses its target list.
    if not targets and set(envs) != {'p', 'v'}:
        listing = run_group(command[:-1] + ['-qp'], cwd=isa, timeout=30, capture=True)
        env_pattern = ''.join(envs)
        selected = sorted(set(re.findall(rf'^(rv{xlen}[a-z0-9]+-[{env_pattern}]-[a-zA-Z0-9_]+):', listing.stdout or '', re.M)))
        if not selected:
            raise ValueError('no upstream ISA targets for selected environments')
        command = command[:-1] + selected
    with (out / 'build.log').open('w') as log:
        result = run_group(command, cwd=isa, timeout=timeout, stdout=log, stderr=log)
    elfs = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(isa.iterdir())
            if is_elf(p)}
    complete = bool(elfs) and (selected == ['all'] or set(selected) <= elfs.keys())
    manifest = dict(schema='rvw.riscv-tests-build/1', status='built' if result.returncode == 0 and not result.timed_out and complete else 'error',
                    source=identity.to_dict(), compiler=dict(path=compiler, sha256=hashlib.sha256(Path(compiler).read_bytes()).hexdigest()),
                    command=command, xlen=xlen, tests=elfs, timed_out=result.timed_out)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest
