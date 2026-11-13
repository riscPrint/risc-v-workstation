"""Short scheduler benchmark. C2 parsing is excluded from these measurements."""
import ctypes as ct
from array import array
import json
import platform
import statistics
from time import perf_counter
from rvw.ooo import native
from rvw.ooo.core import Config, Instruction, simulate


def main():
    native.build(native.library_path())
    c = Config(8, 64, 8, 192, 8, 64, 32, 32, 8,
               dict(zip(native.KINDS, [1, 3, 12, 4, 2, 1, 1])),
               branch_penalty=10, branch_speculation=True)
    results = []
    for name, pattern in [('integer', ('alu',)),
                          ('mixed', ('alu', 'alu', 'load', 'alu', 'store', 'branch'))]:
        ops = [Instruction(pattern[i % len(pattern)], (0,), i % 31 + 1,
                           pc=i*4, next_pc=(i+1)*4) for i in range(5000)]
        times = {b: [] for b in ('python', 'native')}
        for b in times:
            simulate(ops[:1000], c, backend=b)
        for trial in range(4):
            for b in (('python', 'native') if trial % 2 == 0 else ('native', 'python')):
                start = perf_counter()
                result = simulate(ops, c, 2000000, backend=b)
                times[b].append(perf_counter()-start)
        packed = array('q', (v for op in ops for v in
                        (0, 0, op.dest, c.latencies[op.kind], native.KINDS.index(op.kind), 0)))
        data = (native.Op * len(ops)).from_buffer(packed)
        cfg = native.Config(*(getattr(c, k) if k != 'max_cycles' else 2000000
                              for k, _ in native.Config._fields_ if k != 'ports'),
                            (ct.c_int64 * 7)(*([c.issue_width]*7)))
        lib = ct.CDLL(str(native.library_path()))
        lib.rvw_ooo_run.argtypes = [ct.c_int64, ct.POINTER(native.Op),
                                    ct.POINTER(native.Config), ct.POINTER(native.Result)]
        kernel = []
        for _ in range(5):
            r = native.Result()
            start = perf_counter()
            assert lib.rvw_ooo_run(len(ops), data, ct.byref(cfg), ct.byref(r)) == 0
            kernel.append(perf_counter()-start)
            assert r.cycles == result['cycles']
        results.append(dict(kernel_seconds=kernel,
                            kernel_instructions_per_second=len(ops)/statistics.median(kernel), workload=name, instructions=len(ops), cycles=result['cycles'],
                            seconds=times,
                            instructions_per_second={b: len(ops)/statistics.median(t) for b,t in times.items()},
                            speedup=statistics.median(times['python'])/statistics.median(times['native'])))
    print(json.dumps(dict(host=platform.platform(), machine=platform.machine(),
                         method='warmed alternating trials; simulate includes validation and packing; C2 parsing excluded',
                         results=results), indent=2))


if __name__ == '__main__':
    main()
