"""Capture upstream unbounded RVFI checkers for the native engine portfolio."""
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from .riscv import prepare, invoke


def inline(path, directory, stack=()):
    path = Path(path)
    if path in stack:
        raise ValueError('recursive checker include')
    # Upstream testbench has this include under an inactive optional define.
    # Never discard a selected assumption block.
    text = path.read_text()
    if '`define RISCV_FORMAL_ASSUME' in text:
        raise ValueError('optional upstream assume blocks are not supported')
    text = text.replace('`include "assume_stmts.vh"', '')
    return re.sub(r'`include\s+"([^"]+)"',
                  lambda m: inline(directory / m[1], directory, (*stack, path)), text)


def capture(cfg, out):
    """Use genchecks prove mode, not a BMC checker with mode renamed."""
    if any(name != 'cover' and not name.startswith('insn_') for name in cfg['checks']):
        raise ValueError('unbounded capture currently supports instruction checks only')
    if not any(name.startswith('insn_') for name in cfg['checks']):
        raise ValueError('select at least one instruction check')
    out = Path(out).resolve()
    core, identity = prepare(cfg, out)
    file = core / 'checks.cfg'
    file.write_text(file.read_text().replace('[options]\n', '[options]\nmode prove\n', 1))
    with (out / 'generate.log').open('w') as log:
        result = invoke([sys.executable, '../../checks/genchecks.py'], cwd=core,
                        timeout=60, stdout=log, stderr=log)
    if result.returncode or result.timed_out:
        raise ValueError('upstream checker generation failed; see generate.log')
    jobs = []
    for name in cfg['checks']:
        if name == 'cover':
            continue
        if not name.startswith('insn_'):
            raise ValueError('unbounded capture currently supports instruction checks only')
        source = core / 'checks' / (name + '.sby')
        if not source.is_file():
            raise ValueError('missing upstream checker: ' + name)
        with (out / (name + '-setup.log')).open('w') as log:
            result = invoke(['sby', '-f', '--setup', source.name], cwd=source.parent,
                            timeout=30, stdout=log, stderr=log)
        if result.returncode or result.timed_out:
            raise ValueError('SBY capture failed: ' + name)
        directory = source.parent / name / 'src'
        text = inline(directory / (name + '.sv'), directory)
        if '`define RISCV_FORMAL_UNBOUNDED' not in text:
            raise ValueError('upstream did not select unbounded checker semantics')
        for i in range(1, len(cfg['verilog']) + 1):
            text += '\n' + inline(core / f'design{i}.sv', core)
        text += '\n' + inline(core / 'wrapper.sv', core)
        options = cfg.get('check_options', {}).get(name, {})
        text = '\n'.join(options.get('defines', [])) + '\n' + text
        rtl = out / (name + '.sv')
        rtl.write_text(text)
        jobs.append(dict(id=name, top='rvfi_testbench', mode='prove', depth=cfg['depth'],
                         sources=[dict(path=rtl.name, sha256=hashlib.sha256(rtl.read_bytes()).hexdigest())]))
    report = dict(schema='rvw.riscv-proof-capture/1', status='generated', jobs=jobs,
                  formal_inputs=identity,
                  limits=['Unbounded checker capture is not a proof.',
                          'Source assumptions remain restrictions; activation is not certified.',
                          'Retirement cover must be run separately with the bounded runner.'])
    (out / 'capture.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def run(cfg, out, engines, timeout):
    from .portfolio import race, ENGINES
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('timeout must be finite and positive')
    if not 1 <= len(engines) <= 3 or len(set(engines)) != len(engines):
        raise ValueError('select one to three distinct engines')
    if any(e not in ENGINES or 'prove' not in ENGINES[e][2] for e in engines):
        raise ValueError('select known portfolio proof engines')
    out = Path(out).resolve()
    report = capture(cfg, out)
    rows = []
    for plan in report['jobs']:
        plan['engines'] = engines
        (out / (plan['id'] + '.json')).write_text(json.dumps(plan, indent=2) + '\n')
        result = race(plan, out, out / (plan['id'] + '-race'), timeout=timeout)
        rows.append(dict(check=plan['id'], **result))
    report = dict(schema='rvw.riscv-proof/1',
                  status='fail' if any(row['status'] == 'fail' for row in rows) else 'inconclusive', rows=rows,
                  limits=report['limits'])
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
