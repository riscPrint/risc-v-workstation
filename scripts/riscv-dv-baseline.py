#!/usr/bin/env python3
"""Build a small riscv-tests baseline with defined scratch CSR input state."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tomllib


def header(text):
    anchor = '        j reset_vector;'
    if text.count(anchor) != 1:
        raise ValueError('expected one reset-vector jump in the pinned riscv-tests header')
    return text.replace(anchor, '        csrw mscratch, zero; j reset_vector;', 1)


def build(source, settings, out, tests):
    from rvw.common.proc import run_group
    source, settings, out = Path(source).resolve(), Path(settings).resolve(), Path(out).resolve()
    data = tomllib.loads(settings.read_text())
    def path(key):
        return (settings.parent / Path(data[key]).expanduser()).resolve()
    original = source/'env/p/riscv_test.h'
    patched = header(original.read_text())
    out.mkdir(parents=True, exist_ok=False)
    include = out/'include'; (include/'p').mkdir(parents=True)
    (include/'p/riscv_test.h').write_text(patched)
    shutil.copyfile(source/'env/encoding.h', include/'encoding.h')
    elfs = out/'elfs'; elfs.mkdir()
    record = {'source_revision':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),
              'original_header_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
              'patched_header_sha256':hashlib.sha256(patched.encode()).hexdigest(),
              'initial_state':'software writes mscratch before the first reset-vector jump', 'tests':[]}
    for name in tests:
        group, environment, instruction = name.split('-', 2)
        if group not in ('rv32ui','rv32um','rv64ui','rv64um') or environment != 'p':
            raise ValueError('expected physical integer riscv-tests IDs')
        assembly = source/'isa'/group/(instruction+'.S')
        if not assembly.is_file():
            raise ValueError('missing riscv-tests source: '+name)
        argv = [data['compiler'], '-march='+data['isa'], '-mabi='+data['abi'],
                '-mcmodel=medany', '-nostdlib', '-nostartfiles', '-static',
                '-I',str(include/'p'), '-I',str(source/'isa/macros/scalar'),
                '-T',str(path('linker')),str(assembly),'-o',str(elfs/name)]
        with (out/(name+'.log')).open('w') as log:
            result = run_group(['nice','-n','10',*argv],timeout=30,stdout=log,stderr=log)
        if result.timed_out or result.returncode:
            raise ValueError('baseline compile failed: '+name)
        record['tests'].append({'id':name, 'argv':argv, 'elf_sha256':hashlib.sha256((elfs/name).read_bytes()).hexdigest()})
    (out/'build.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--settings', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('tests', nargs='+')
    a = p.parse_args()
    build(a.source, a.settings, a.out, a.tests)
