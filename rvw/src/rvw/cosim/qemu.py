"""Bounded single-hart QEMU CPU-log observations for boot trace comparison."""
import hashlib
import json
from pathlib import Path
import re
from .trace import Trace

PC = re.compile(r'\s*pc\s+([0-9a-fA-F]+)\s*$')
REG = re.compile(r'x(\d+)/\w+\s+([0-9a-fA-F]+)')


def snapshots(path):
    """Read QEMU `-d cpu` with TCG one-insn-per-tb=on and -smp 1."""
    state = None
    with Path(path).open() as stream:
        for line in stream:
            match = PC.fullmatch(line)
            if match:
                if state is not None:
                    if set(state['regs']) != set(range(32)):
                        raise ValueError('QEMU CPU snapshot lacks complete integer registers')
                    yield state
                state = dict(pc=int(match[1], 16), regs={})
            elif state is not None:
                for index, value in REG.findall(line):
                    index = int(index)
                    if not 0 <= index < 32:
                        raise ValueError('invalid QEMU integer register')
                    state['regs'][index] = int(value, 16)
        if state is not None:
            if set(state['regs']) != set(range(32)):
                raise ValueError('QEMU CPU snapshot lacks complete integer registers')
            yield state


def compare(trace_path, log, *, max_prefix=4096):
    if max_prefix < 0:
        raise ValueError('max_prefix must be nonnegative')
    with Path(log).open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    with Path(trace_path).open('rb') as stream:
        trace_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = dict(trace_sha256=trace_digest, schema='rvw.qemu-observation/1', model='qemu', log_sha256=digest,
                  scope='PC, next PC, integer source values and integer destination values',
                  architectural_match=False,
                  unchecked=['instruction_bits', 'memory', 'CSRs', 'FP', 'vector', 'hypervisor', 'debug'])
    states = iter(snapshots(log))
    current, compared, skipped, complete = None, 0, 0, False
    trace = Trace(trace_path)
    try:
        if trace.multihart:
            raise ValueError('QEMU observation comparison requires a single hart')
        for actual in trace:
            event = actual.get('event')
            if event == 'end':
                complete = True
                continue
            if event or actual['intr']:
                return dict(report, status='inconclusive', cause='event_synchronization_unsupported', instructions=compared)
            if current is None:
                current = next(states, None)
                while current is not None and current['pc'] != actual['pc'] and skipped < max_prefix:
                    current = next(states, None)
                    skipped += 1
            following = next(states, None)
            if current is None or following is None:
                return dict(report, status='inconclusive', cause='qemu_log_ended', instructions=compared)
            expected = dict(pc=current['pc'], pc_next=following['pc'],
                            rs1_rdata=current['regs'][actual['rs1']],
                            rs2_rdata=current['regs'][actual['rs2']])
            if actual['rd']:
                expected['rd_wdata'] = following['regs'][actual['rd']]
            diff = {key: dict(expected=hex(value), actual=hex(actual[key]))
                    for key, value in expected.items() if actual[key] != value}
            if diff:
                return dict(report, status='mismatch', instructions=compared, skipped_prefix=skipped,
                            mismatch=dict(order=actual['order'], cycle=actual['cycle'], differences=diff))
            compared += 1
            current = following
        return dict(report, status='match' if complete and compared else 'inconclusive',
                    instructions=compared, trace_complete=complete, skipped_prefix=skipped)
    finally:
        trace.close()
        states.close()


def execute_json(**options):
    try:
        return compare(options['trace'], options['log'], max_prefix=options.get('max_prefix', 4096))
    except (OSError, ValueError, KeyError) as exc:
        return dict(schema='rvw.qemu-observation/1', status='error', message=str(exc))


def register(subs):
    parser = subs.add_parser('qemu-check', help='compare a bounded boot trace with QEMU CPU observations')
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--max-prefix', type=int, default=4096)
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def run(args):
    result = execute_json(trace=args.trace, log=args.log, max_prefix=args.max_prefix)
    print(json.dumps(result))
    return {'match': 0, 'mismatch': 1, 'error': 2, 'inconclusive': 3}[result['status']]


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.mcp.worker import handler
    return [ToolSpec('cosim_qemu_check', 'Compare bounded single-hart C2 boot traces with QEMU single-step CPU logs. Checks PC and integer observations only. Async events remain inconclusive.',
        schema(dict(trace={'type': 'string'}, log={'type': 'string'}, max_prefix={'type': 'integer', 'minimum': 0, 'default': 4096}), ['trace', 'log']), handler('rvw.cosim.qemu'), long=True)]
