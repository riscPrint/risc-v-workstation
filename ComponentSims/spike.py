#!/usr/bin/env python3
"""Run a native direction study from checked workload Spike evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

LINE = re.compile(r'core\s+(\d+):\s+0x([0-9a-fA-F]+)\s+\(0x([0-9a-fA-F]+)\)')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def signed(value, width):
    return value - (1 << width) if value & (1 << (width-1)) else value


def target(pc, bits):
    """Return conditional target only. Decode RV64 B and C.BEQZ/C.BNEZ."""
    if bits & 3 == 3:
        if bits & 127 != 0x63:
            return None
        if (bits >> 12) & 7 not in (0, 1, 4, 5, 6, 7):
            raise ValueError('reserved conditional branch')
        imm = ((bits >> 31) & 1) << 12 | ((bits >> 7) & 1) << 11
        imm |= ((bits >> 25) & 63) << 5 | ((bits >> 8) & 15) << 1
        return (pc + signed(imm, 13)) & ((1 << 64)-1)
    if bits & 3 == 1 and (bits >> 13) & 7 in (6, 7):
        imm = ((bits >> 12) & 1) << 8 | ((bits >> 10) & 3) << 3
        imm |= ((bits >> 5) & 3) << 6 | ((bits >> 3) & 3) << 1 | ((bits >> 2) & 1) << 5
        return (pc + signed(imm, 9)) & ((1 << 64)-1)
    return None


def convert(source, destination):
    """Stream one hart. Reject ambiguous successors and incomplete branches."""
    count, hart, previous = 0, None, None
    destination = Path(destination)
    # Spool branch rows until the full instruction denominator is known.
    with tempfile.TemporaryFile(mode='w+t') as rows:
        with Path(source).open(errors='strict') as stream:
            for line in stream:
                if re.search(r'\b(exception|trap_)', line):
                    raise ValueError('exception in Spike instruction log')
                match = LINE.match(line)
                if not match:
                    if re.match(r'core\s+\d+:\s+0x', line):
                        raise ValueError('malformed Spike instruction row')
                    continue
                row_hart, pc, bits = (int(x, base) for x, base in zip(match.groups(), (10, 16, 16)))
                if hart is None:
                    hart = row_hart
                if hart != row_hart:
                    raise ValueError('multiple harts are unsupported')
                if bits > 0xffffffff or pc > 0xffffffffffffffff or pc & 1:
                    raise ValueError('unsupported instruction or PC')
                if previous is not None:
                    ordinal, old_pc, fallthrough, branch_target = previous
                    if branch_target == fallthrough or pc not in (fallthrough, branch_target):
                        raise ValueError('ambiguous branch successor')
                    rows.write(f'B {ordinal} {old_pc:x} {int(pc == branch_target)}\n')
                count += 1
                branch_target = target(pc, bits)
                previous = ((count, pc, (pc + (4 if bits & 3 == 3 else 2)) & ((1 << 64)-1), branch_target)
                            if branch_target is not None else None)
        if not count or previous is not None:
            raise ValueError('empty log or terminal branch without successor')
        rows.seek(0)
        with destination.open('x') as output:
            output.write(f'rvw.branch-trace/1 {count}\n')
            for line in rows:
                output.write(line)
            output.write('END\n')
    return count


def select(report_path, workload):
    report_path = Path(report_path).resolve()
    data = json.loads(report_path.read_bytes())
    if data.get('schema') != 'rvw.workload-verify/1' or data.get('status') != 'pass':
        raise ValueError('require a successful workload verification report')
    if Path(data['oracle']['path']).name != 'spike':
        raise ValueError('require Spike evidence')
    rows = [r for r in data['workloads'] if r['id'] == workload]
    if len(rows) != 1:
        raise ValueError('require exactly one selected workload')
    row = rows[0]
    if row.get('status') != 'pass' or row.get('exit_code') != 0 or row.get('timed_out') is not False or not row.get('profile'):
        raise ValueError('require a completed traced workload')
    if Path(workload).name != workload or workload in ('.', '..'):
        raise ValueError('invalid workload name')
    source = report_path.parent / (workload + '.stderr')
    if digest(source) != row['stderr_sha256']:
        raise ValueError('Spike log hash mismatch')
    return source, row, data['oracle']


def study(report, workload, engine, out, model='gshare', entries=4096,
          history=12, pc_shift=1, warmup=0):
    report, engine, out = Path(report).resolve(), Path(engine).resolve(), Path(out).resolve()
    report_hash, engine_hash = digest(report), digest(engine)
    source, row, oracle = select(report, workload)
    out.mkdir(parents=True, exist_ok=False)
    trace = out / 'trace.txt'
    count = convert(source, trace)
    if count != row['profile']['counts']['instructions']:
        raise ValueError('instruction count differs from verified profile')
    trace_hash = digest(trace)
    with trace.open() as stream:
        result = subprocess.run([str(engine), model, str(entries), str(history),
                                 str(pc_shift), str(warmup)], stdin=stream,
                                text=True, capture_output=True, timeout=120)
    if result.returncode:
        raise ValueError(result.stderr.strip())
    data = json.loads(result.stdout)
    if digest(source) != row['stderr_sha256'] or digest(report) != report_hash or digest(engine) != engine_hash or digest(trace) != trace_hash:
        raise ValueError('evidence changed during study')
    data.update(workload=workload, elf_sha256=row['elf_sha256'],
                scope='whole-program including startup and checker', oracle=oracle,
                verify={'path': str(report), 'sha256': report_hash},
                source={'path': str(source), 'sha256': row['stderr_sha256']},
                trace={'path': str(trace), 'sha256': trace_hash},
                engine={'path': str(engine), 'sha256': engine_hash},
                adapter_sha256=digest(__file__))
    (out / 'report.json').write_text(json.dumps(data, indent=2) + '\n')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path, required=True)
    parser.add_argument('--workload', required=True)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model', choices=['bimodal', 'gshare', 'perfect'], default='gshare')
    parser.add_argument('--entries', type=int, default=4096)
    parser.add_argument('--history', type=int, default=12)
    parser.add_argument('--pc-shift', type=int, default=1)
    parser.add_argument('--warmup', type=int, default=0)
    args = parser.parse_args()
    try:
        data = study(args.verify, args.workload, args.engine, args.out, args.model,
                     args.entries, args.history, args.pc_shift, args.warmup)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({'error': str(error)}))
        return 2
    print(json.dumps(data))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
