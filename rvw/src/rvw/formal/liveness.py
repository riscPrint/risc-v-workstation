"""Clocked response liveness through native live or liveness-to-safety jobs.

Progress automata retain overlapping obligations. The acceptance predicate
must hold infinitely often. No finite deadline substitutes for eventuality.
"""
import json
from pathlib import Path
import re

from rvw.common.proc import run_group
from .temporal import Unsupported, lower, unwrap
from .sva import _group
from .unbounded import MARKER, emit


def lower_live(source, top):
    from .property_names import expand
    source = expand(source, lambda body: True)
    text = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: ' ' * len(m[0]), source, flags=re.S)
    if re.search(r'\brvw_live_\w*', text):
        raise Unsupported('reserved_identifier', 'rvw_live_')
    module = re.search(r'\bmodule\s+' + re.escape(top) + r'\b.*?\bendmodule\b', text, re.S)
    if not module:
        raise ValueError('top module not found')
    edits, rows, clocks = [], [], set()
    for index, match in enumerate(re.finditer(r'\b(assert|assume)\s+property\s*\(', module[0])):
        start = module.start() + match.start()
        body, end = _group(text, module.start() + match.end() - 1)
        if not MARKER.search(body):
            continue
        clock = re.match(r'\s*@\(\s*posedge\s+(\w+)\s*\)\s*', body)
        if not clock:
            raise Unsupported('liveness_clock')
        clocks.add(clock[1])
        expr = unwrap(body[clock.end():])
        semi = re.match(r'\s*;', text[end:])
        if not semi:
            raise Unsupported('action_block')
        # Remove a source label before inserting declarations.
        label = re.search(r'\b(\w+)\s*:\s*$', text[module.start():start])
        name = label[1] if label else f'liveness_{index}'
        if label:
            start = module.start() + label.start()
        prefix = f'rvw_live_{index}'
        emitted, details = emit(expr, clock[1], prefix)
        edits.append((start, end + semi.end(), emitted))
        rows.append(dict(id=name, wire=prefix, clock=clock[1],
                         kind='live' if match[1] == 'assert' else 'fair', **details))
    if not rows:
        raise Unsupported('liveness_form', 'no supported unbounded temporal properties')
    if len(clocks) != 1:
        raise Unsupported('liveness_multiclock')
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    remaining = re.sub(r'//[^\n]*|/\*.*?\*/', ' ', source, flags=re.S)
    if re.search(r'\b(assert|assume|cover)\s*\(', remaining):
        raise Unsupported('mixed_liveness_safety', 'native checks need a separate job')
    # Validate the remaining source. Keep finite property jobs separate.
    source, finite = lower(source)
    if finite:
        raise Unsupported('mixed_liveness_safety', 'run finite safety statements in a separate job')
    return source, rows, finite


def script(top, rows):
    commands = ['read -formal lowered.sv', f'prep -top {top}', f'select -module {top}']
    commands += [f'add -{row["kind"]} {row["wire"]}' for row in rows]
    commands += ['select *']
    return '\n'.join(commands)


def run(args):
    from .common import sigterm_raises
    with sigterm_raises():
        return _run(args)


def _run(args):
    from . import common
    from rvw.common.capture import Capture
    out = common.check_path('--out', args.out)
    common.check_ident('top', args.top)
    lock = common.lock_out(out)
    try:
        (out / 'result.json').unlink(missing_ok=True)
        capture = Capture(out / 'inputs')
        item = capture.file(Path(args.source))
        source, rows, finite = lower_live(item.copy.read_text(), args.top)
        (out / 'lowered.sv').write_text(source)
        job = '[options]\nmode live\n[engines]\naiger suprove\n[script]\n' + script(args.top, rows) + '\n[files]\nlowered.sv\n'
        (out / 'job.sby').write_text(job)
        result = dict(schema='rvw.formal-live/1', status='unknown',
                      observation='not_run', properties=rows, finite_properties=finite,
                      restrictions=['Single abstract rising-edge clock; no disable iff.',
                                    'Engine results do not certify attribution or non-vacuity.'],
                      input_capture=capture.record())
        backend = getattr(args, 'backend', 'suprove')
        result['backend'] = backend
        if args.run and not any(row['kind'] == 'live' for row in rows):
            result['observation'] = 'no_checks'
        elif backend == 'l2s':
            result['restrictions'] += [
                'One active-high startup reset cycle, then reset remains deasserted.',
                'Synchronous finite-state canonical-range model; job engine limits still apply.']
            from . import liveness_safety
            detail = liveness_safety.run(out, args.top, rows, capture, args)
            result.update(detail)
            result['input_capture'] = capture.record()
            if result['observation'] == 'FAIL':
                result['status'] = 'fail'
        elif args.run:
            import shutil
            if not shutil.which('suprove') or not shutil.which('sby'):
                result['observation'] = 'missing_tool'
            else:
                status = out / 'job/status'
                status.unlink(missing_ok=True)
                with (out / 'run.log').open('w') as log:
                    completed = run_group(['sby', '-f', 'job.sby'], cwd=out, stdout=log,
                                          stderr=log, timeout=args.timeout)
                status = out / 'job/status'
                result['observation'] = ('timeout' if completed.timed_out else
                                         status.read_text().split()[0] if status.exists() else 'error')
                if result['observation'] == 'PASS' and completed.returncode != 0:
                    result['observation'] = 'error'
                if result['observation'] == 'FAIL':
                    result['status'] = 'fail'
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
        return 1 if args.run else 0
    finally:
        import os
        os.close(lock)
