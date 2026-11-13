#!/usr/bin/env python3
"""Run the pinned upstream base generator natively, without a process pool.

This bounded profile generates integer ALU programs. It does not implement a
new instruction generator. Compile the output with the core project's runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys

REVISION = 'f557b89ed6881a20515481a2585e9d004cd9642b'


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkout', type=Path, required=True)
    p.add_argument('--python', default=sys.executable)
    p.add_argument('--target', choices=['rv32imc', 'rv64imc'], required=True)
    p.add_argument('--test-class', choices=['arithmetic', 'branches', 'load-store'], default='arithmetic')
    p.add_argument('--target-profile', type=Path)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--instructions', type=int, default=50)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=120)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    return p


def worker(a):
    from importlib.metadata import version
    os.chdir(a.checkout)
    sys.path.insert(0, str(a.checkout / 'pygen'))
    # Seed before constructing PyVSC objects, as well as before generation.
    random.seed(str(a.seed))
    import pyboolector
    if version('pyboolector') != '3.2.4.38488416565':
        raise ValueError('use pyboolector==3.2.4.38488416565')
    if version('pyvsc') != '0.9.1.10086043874':
        raise ValueError('use pyvsc==0.9.1.10086043874')
    # PyVSC's two old option names moved into BtorOption. Values are unchanged.
    for name in ('BTOR_OPT_INCREMENTAL', 'BTOR_OPT_MODEL_GEN'):
        setattr(pyboolector, name, getattr(pyboolector.BtorOption, name))
    sys.argv = ['pygen', '--target='+a.target, '--gen_test=rvw_single_process',
                '--seed='+str(a.seed), '--instr_cnt='+str(a.instructions),
                '--num_of_sub_program=0', '--no_branch_jump='+str(int(a.test_class != 'branches')),
                '--no_load_store='+str(int(a.test_class != 'load-store')),
                '--disable_compressed_instr=1', '--bare_program_mode=1',
                '--asm_file_name='+str(a.out/'program'),
                '--log_file_name='+str(a.out/'generator.log')]
    if a.test_class == 'branches':
        sys.argv += ['--directed_instr_0=riscv_jal_instr,20']
    elif a.test_class == 'load-store':
        sys.argv += ['--directed_instr_0=riscv_load_store_rand_instr_stream,20',
                     '--directed_instr_1=riscv_load_store_hazard_instr_stream,20']
    if a.target_profile:
        from importlib import import_module
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'rvw/src'))
        from rvw.regress.dv_target import apply
        package = import_module('pygen_src.riscv_instr_pkg')
        module = import_module('pygen_src.target.'+a.target+'.riscv_core_setting')
        target = json.loads(a.target_profile.read_text())
        apply(target, module, package)
        sys.argv += ['--enable_unaligned_load_store='+str(int(target['unaligned_load_store']))]
    if a.test_class == 'load-store':
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'rvw/src'))
        from rvw.regress.dv_compat import install_load_store_fix
        install_load_store_fix()
    # The pinned base class has no directed streams and honors instr_cnt.
    # The upstream rand test overrides it to 10,000 and adds directed streams.
    from pygen_src.test.riscv_instr_base_test import riscv_instr_base_test
    riscv_instr_base_test()._run_phase(0)


def main():
    a = parser().parse_args()
    a.checkout = a.checkout.resolve()
    a.out = a.out.resolve()
    if a.worker:
        worker(a)
        return 0
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'rvw/src'))
    from rvw.common.proc import run_group
    import math
    if not 1 <= a.instructions <= 1000 or not math.isfinite(a.timeout) or a.timeout <= 0:
        raise ValueError('instructions must be 1..1000; timeout must be finite and positive')
    revision = subprocess.check_output(['git', '-C', str(a.checkout), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(a.checkout), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if revision != REVISION or dirty:
        raise ValueError('generator checkout must be clean at '+REVISION)
    a.out.mkdir(parents=True, exist_ok=False)
    extra = ['--target-profile', str(a.target_profile.resolve())] if a.target_profile else []
    with (a.out/'worker.log').open('w') as log:
        r = run_group([a.python, str(Path(__file__).resolve()), '--worker',
                       '--checkout', str(a.checkout), '--target', a.target,
                       '--seed', str(a.seed), '--instructions', str(a.instructions),
                       '--out', str(a.out), '--test-class', a.test_class, *extra], timeout=a.timeout, stdout=log, stderr=log)
    source = a.out/'program_0.S'
    metadata = dict(status='generated' if not r.timed_out and r.returncode == 0 and source.is_file() else 'error',
                    generator_revision=revision, target=a.target, seed=a.seed,
                    instructions=a.instructions, profile='bare-integer-alu' if a.test_class == 'arithmetic' else 'bare-'+a.test_class,
                    test_class=a.test_class,
                    pyboolector='3.2.4.38488416565', pyvsc='0.9.1.10086043874',
                    returncode=r.returncode, timed_out=r.timed_out)
    if a.test_class == 'load-store':
        metadata['compatibility_sha256'] = hashlib.sha256((Path(__file__).resolve().parents[1]/'rvw/src/rvw/regress/dv_compat.py').read_bytes()).hexdigest()
    if a.target_profile:
        metadata['target_profile_sha256'] = hashlib.sha256(a.target_profile.read_bytes()).hexdigest()
    if source.is_file():
        metadata['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    (a.out/'generation.json').write_text(json.dumps(metadata, indent=2)+'\n')
    print(json.dumps(metadata))
    return 0 if metadata['status'] == 'generated' else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
