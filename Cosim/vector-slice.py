#!/usr/bin/env python3
"""Build one pinned upstream vadd.vv slice and replay its C2 with fresh Spike."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'rvw/src'))
from rvw.common.proc import run_group
from rvw.cosim.vector_source import REVISION, ENV_REVISION
from rvw.cosim.cli import execute_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    if ROOT in source.parents or ROOT in out.parents:
        raise ValueError('keep sources and generated evidence outside the workstation')
    def run(command, cwd=None):
        r = run_group(list(map(str, command)), cwd=cwd, capture=True, timeout=180)
        if r.timed_out or r.returncode:
            raise ValueError(str(r.stderr or r.stdout or 'command timed out'))
        return r.stdout.strip()
    for path, revision in ((source, REVISION), (source/'env/riscv-test-env', ENV_REVISION)):
        if run(['git', '-C', path, 'rev-parse', 'HEAD']) != revision:
            raise ValueError('source revision differs from pinned vector source')
    out.mkdir(parents=True, exist_ok=False)
    run(['nice', '-n', '10', 'go', 'build', '-o', out/'single', './single'], cwd=source)
    run(['nice', '-n', '10', out/'single', '-VLEN', '128', '-XLEN', '64', '-split', '2000',
         '-configfile', source/'configs/v/vadd.vv.toml', '-outputfile', out/'vadd.S'])
    gcc = os.environ.get('RISCV_GCC') or shutil.which('riscv64-unknown-elf-gcc')
    if not gcc:
        raise ValueError('set RISCV_GCC or put the RISC-V compiler on PATH')
    run(['nice', '-n', '10', gcc, '-march=rv64gcv', '-mabi=lp64d', '-static', '-mcmodel=medany',
         '-nostdlib', '-nostartfiles', '-DCOSIM_TEST_CASE', '-I', source/'env/riscv-test-env/p',
         '-I', source/'macros/general', '-T', source/'env/riscv-test-env/p/link.ld',
         out/'vadd.S', '-o', out/'vadd'])
    platform = out/'platform.json'
    platform.write_text(json.dumps(dict(name='vector-reference', xlen=64, isa='rv64gcv_zicsr_zifencei',
        reset_pc='0x80000000', ram=[dict(base='0x80000000',size='0x1000000')], mmio=[], pmp_regions=16)))
    options = dict(core='vector-reference', platform=str(platform), elf=str(out/'vadd'))
    generated = execute_json('generate', **options, out=str(out/'rvfi.jsonl'), max_instructions=100000)
    (out/'generated.json').write_text(json.dumps(generated, indent=2)+'\n')
    if generated.get('termination') != 'pass':
        raise ValueError('reference generation did not finish: '+json.dumps(generated))
    checked = execute_json('check', **options, trace=str(out/'rvfi.jsonl'), strict=True)
    report = dict(schema='rvw.vector-slice/1', source_revision=REVISION, env_revision=ENV_REVISION,
                  dut=False, scope='upstream vadd.vv first generated slice; Spike-to-Spike C2 replay',
                  generation=generated, comparison=checked)
    (out/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report))
    return 0 if checked.get('status') == 'match' and checked.get('trace_complete') else 1


if __name__ == '__main__':
    sys.exit(main())
