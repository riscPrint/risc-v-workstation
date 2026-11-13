"""Optional C scheduler. Unsupported configurations use the Python engine."""
from array import array
from itertools import chain
import ctypes as ct
import os
from pathlib import Path
import subprocess
import sys


class Op(ct.Structure):
    _fields_ = [(k, ct.c_int64) for k in ('src0', 'src1', 'dest', 'latency', 'kind', 'miss')]


class Config(ct.Structure):
    _fields_ = [(k, ct.c_int64) for k in ('fetch_width', 'fetch_entries', 'rename_width',
        'rob_entries', 'issue_width', 'issue_entries', 'commit_width', 'physical_registers', 'max_cycles',
        'load_entries', 'store_entries', 'branch_penalty', 'branch_speculation')] + [('ports', ct.c_int64 * 7)]


class Result(ct.Structure):
    _fields_ = [(k, ct.c_int64) for k in ('cycles', 'issued', 'dependency_blocked', 'rob_full',
        'issue_full', 'register_full', 'peak_rob', 'peak_issue', 'peak_fetch', 'retiring', 'frontend', 'backend', 'bad_speculation', 'loads', 'stores',
        'load_full', 'store_full', 'branches', 'branch_misses', 'wrong_path_fetch_slots_estimate',
        'port_blocked', 'correct_path_speculative_issues')]


def library_path():
    return Path(os.environ.get('RVW_OOO_NATIVE', Path(__file__).resolve().parents[4] / '.tools/ooo/libooo.so'))


def build(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name('native.c')
    compiler = os.environ.get('CC', 'cc')
    subprocess.run([compiler, '-O3', '-std=c11', '-fPIC',
                    '-dynamiclib' if sys.platform == 'darwin' else '-shared',
                    str(source), '-o', str(path)], check=True, timeout=120)
    return path


KINDS = ("alu", "multiply", "divide", "load", "store", "branch", "jump")


def simulate(ops, config, max_cycles):
    if (config.memory_rename or config.components or config.frontend or config.execution or config.translation or config.rename or config.memory_policy != "ordered" or
        any(op.kind not in KINDS or len(op.sources) > 2 or (op.dest is not None and op.dest >= 32) or any(r >= 32 for r in op.sources) for op in ops)):
        return None
    if os.environ.get('RVW_OOO_NATIVE') == '0' or not library_path().is_file():
        return None
    lib = ct.CDLL(str(library_path()))
    lib.rvw_ooo_abi.restype = ct.c_int
    if lib.rvw_ooo_abi() != 2:
        raise ValueError('unsupported native OoO ABI')
    lib.rvw_ooo_run.argtypes = [ct.c_int64, ct.POINTER(Op), ct.POINTER(Config), ct.POINTER(Result)]
    lib.rvw_ooo_run.restype = ct.c_int
    packed = array("q", chain.from_iterable(
        (op.sources[0] if op.sources else 0, op.sources[1] if len(op.sources) > 1 else 0,
         op.dest or 0, config.latencies[op.kind], KINDS.index(op.kind),
         int(op.next_pc != op.pc + op.length)) for op in ops))
    data = (Op * len(ops)).from_buffer(packed)
    c = Config(*(getattr(config, k) if k != 'max_cycles' else max_cycles for k, _ in Config._fields_ if k != 'ports'),
               (ct.c_int64 * 7)(*(config.ports.get(k, config.issue_width) for k in KINDS)))
    r = Result()
    status = lib.rvw_ooo_run(len(ops), data, ct.byref(c), ct.byref(r))
    if status:
        raise ValueError('model cycle budget exhausted' if status == 1 else 'native scheduler allocation failed')
    from .attribution import Attribution
    a = Attribution(config.commit_width)
    a.slots.update(retiring=r.retiring, frontend_bound=r.frontend, backend_bound=r.backend, bad_speculation=r.bad_speculation)
    events = {k: getattr(r, k) for k in ('issued', 'dependency_blocked', 'rob_full', 'issue_full', 'register_full', 'load_full', 'store_full', 'branches', 'branch_misses',
        'port_blocked', 'correct_path_speculative_issues') if getattr(r, k)}
    if r.branch_misses:
        events["wrong_path_fetch_slots_estimate"] = r.wrong_path_fetch_slots_estimate
    # Python preserves its dependency counter even when zero.
    events.setdefault('dependency_blocked', 0)
    return dict(cycles=r.cycles, instret=len(ops), ipc=len(ops)/r.cycles,
                events=events, max_occupancy=dict(rob_entries=r.peak_rob, issue_entries=r.peak_issue,
                fetch_entries=r.peak_fetch, load_entries=r.loads, store_entries=r.stores, decode_entries=0), topdown=a.report())


if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] not in ('--build', '--check'):
        raise SystemExit('usage: python -m rvw.ooo.native --build|--check LIBRARY')
    if sys.argv[1] == '--build':
        print(build(sys.argv[2]))
    else:
        library = ct.CDLL(str(Path(sys.argv[2]).resolve()))
        if library.rvw_ooo_abi() != 2:
            raise SystemExit('unsupported native OoO ABI')
        print('PRESENT native OoO scheduler ABI 2')
