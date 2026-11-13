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
                    str(source), str(source.with_name('native_c2.c')), str(source.with_name('native_decode.c')), '-o', str(path)], check=True, timeout=120)
    return path


KINDS = ("alu", "multiply", "divide", "load", "store", "branch", "jump")


def supported(config):
    return not (config.replay_at_commit or config.retry_costs or config.replay_window or config.cache_miss_replay or config.store_drain_width or config.wrong_path_occupancy or config.issue_queue_policy != "associative" or config.branch_prediction != "sequential" or config.issue_order != "out_of_order" or config.memory_rename or config.frontend or config.execution or config.translation
                or config.rename or config.memory_policy != "ordered" or config.store_policy != "ordered" or config.custom_instructions
                or any(k not in ('branch', 'btb', 'ras', 'indirect', 'memory') for k in config.components)
                or config.components.get('memory', {}).get('l1i'))


class Packed:
    def __init__(self, data, info, count, decoder="python-template"):
        self.data, self.info, self.count = data, info, count
        self.decoder = decoder

    def __len__(self):
        return self.count


def parse_c2(data, config):
    """Parse the flat C2/1 subset. Return None for shared-validator fallback."""
    if not supported(config) or os.environ.get('RVW_OOO_NATIVE') == '0' or not library_path().is_file():
        return None
    lib = ct.CDLL(str(library_path()))
    if not hasattr(lib, 'rvw_ooo_parse_c2'):
        return None
    from io import StringIO
    from rvw.cosim.trace import Trace
    from rvw.common.riscv import decode
    from rvw.csim.traces import branch_kind
    from rvw.csim.lib import KINDS as BRANCH_KINDS
    offset = data.find(b'\n')
    if offset < 0:
        return None
    trace = Trace(StringIO(data[:offset].decode()))
    h = trace.header
    trace.close()
    if h['schema'] != 'rvw.rvfi/1' or trace.multihart or h.get('csr_snapshot'):
        return None
    capacity = data.count(b'\n') + 1
    packed, info = (Op * capacity)(), (ct.c_uint64 * (capacity*6))()
    callback_type = ct.CFUNCTYPE(ct.c_int, ct.c_uint32, ct.c_int, ct.POINTER(Op), ct.POINTER(ct.c_uint64))
    branch = any(k in config.components for k in ('branch', 'btb', 'ras', 'indirect'))
    if hasattr(lib, 'rvw_ooo_parse_c2_native'):
        fn = lib.rvw_ooo_parse_c2_native
        fn.argtypes = [ct.c_char_p, ct.c_size_t, ct.c_int, ct.POINTER(Op), ct.POINTER(ct.c_uint64),
                       ct.c_int64, ct.POINTER(ct.c_int64), ct.c_int]
        fn.restype = ct.c_int64
        latencies = (ct.c_int64 * len(KINDS))(*(config.latencies.get(k,0) for k in KINDS))
        count = fn(data, len(data), h['xlen'], packed, info, capacity, latencies, int(branch))
        if count > 0:
            return Packed(packed, info, count, decoder='native-imc')
    def template(word, rd, out, meta):
        d = decode(word, h['xlen'])
        if d.cls not in KINDS or d.cls not in config.latencies or d.dest_bank != 'x' or any(b != 'x' for b, _ in d.sources):
            return -1
        sources = [r for _, r in d.sources]
        out[0] = Op(*(sources+[0,0])[:2], rd, config.latencies[d.cls], KINDS.index(d.cls), 0)
        meta[0] = d.length
        meta[1] = BRANCH_KINDS[branch_kind(word, rd, h['xlen']) or ('cond' if d.cls == 'branch' else 'jump')] if branch and d.cls in ('branch', 'jump') else 0
        return 0
    callback = callback_type(template)
    lib.rvw_ooo_parse_c2.argtypes = [ct.c_char_p, ct.c_size_t, ct.c_int, ct.POINTER(Op), ct.POINTER(ct.c_uint64), ct.c_int64, callback_type]
    lib.rvw_ooo_parse_c2.restype = ct.c_int64
    count = lib.rvw_ooo_parse_c2(data, len(data), h['xlen'], packed, info, capacity, callback)
    return Packed(packed, info, count) if count > 0 else None


def simulate(ops, config, max_cycles):
    if not supported(config):
        return None
    if not isinstance(ops, Packed) and any(op.kind not in KINDS or len(op.sources) > 2 or (op.dest is not None and op.dest >= 32) or any(r >= 32 for r in op.sources) for op in ops):
        return None
    if os.environ.get('RVW_OOO_NATIVE') == '0' or not library_path().is_file():
        return None
    lib = ct.CDLL(str(library_path()))
    if config.components and not hasattr(lib, 'rvw_ooo_run_components'):
        return None
    lib.rvw_ooo_abi.restype = ct.c_int
    if lib.rvw_ooo_abi() != 2:
        raise ValueError('unsupported native OoO ABI')
    lib.rvw_ooo_run.argtypes = [ct.c_int64, ct.POINTER(Op), ct.POINTER(Config), ct.POINTER(Result)]
    lib.rvw_ooo_run.restype = ct.c_int
    if isinstance(ops, Packed):
        data = ops.data
    else:
        packed = array("q", chain.from_iterable(
            (op.sources[0] if op.sources else 0, op.sources[1] if len(op.sources) > 1 else 0,
             op.dest or 0, config.latencies[op.kind], KINDS.index(op.kind),
             int(op.next_pc != op.pc + op.length)) for op in ops))
        data = (Op * len(ops)).from_buffer(packed)
    c = Config(*(getattr(config, k) if k != 'max_cycles' else max_cycles for k, _ in Config._fields_ if k != 'ports'),
               (ct.c_int64 * 7)(*(config.ports.get(k, config.issue_width) for k in KINDS)))
    r = Result()
    component_stats, component_events = None, {}
    if config.components:
        from rvw.csim.lib import Components, KINDS as BRANCH_KINDS
        from rvw.csim.traces import branch_kind
        branch = any(k in config.components for k in ('branch', 'btb', 'ras', 'indirect'))
        if isinstance(ops, Packed):
            extra = ops.info
        else:
            info = array('Q', chain.from_iterable(
                (op.pc, op.next_pc, op.length, op.address or 0, op.size,
                 BRANCH_KINDS[('call' if op.mnemonic == 'c.jal' else branch_kind(op.encoding, op.dest or 0))
                              or ('cond' if op.kind == 'branch' else 'jump')]
                 if branch and op.kind in ('branch', 'jump') else 0) for op in ops))
            extra = (ct.c_uint64 * len(info)).from_buffer(info)
        counts = (ct.c_int64 * 18)()
        with Components(config.components) as models:
            fn = lib.rvw_ooo_run_components
            fn.argtypes = [ct.c_int64, ct.POINTER(Op), ct.POINTER(Config), ct.POINTER(Result),
                           ct.POINTER(ct.c_uint64), ct.c_void_p, ct.c_void_p, ct.POINTER(ct.c_int64)]
            fn.restype = ct.c_int
            status = fn(len(ops), data, ct.byref(c), ct.byref(r), extra, models._h,
                        ct.cast(models._lib.csim_ooo_service, ct.c_void_p), counts)
            component_stats = models.stats(len(ops))
        if branch:
            component_events['btb_lookup_delay_cycles'] = counts[0]
            if counts[1]:
                component_events['btb_misses'] = counts[1]
            component_events.update({f'btb_level_{i}_hits': counts[i+2] for i in range(16) if counts[i+2]})
    else:
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
    if component_stats is not None:
        from .component_events import counters
        events.update(component_events)
        events.update(counters(component_stats))
    return dict(**({'components': component_stats} if component_stats is not None else {}), cycles=r.cycles, instret=len(ops), ipc=len(ops)/r.cycles,
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
