#!/usr/bin/env python3
"""Measure an indexed waveform in fresh processes. Results are fixture evidence."""
import argparse
import json
from pathlib import Path
import resource
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory', type=Path)
    p.add_argument('--updates', type=int, default=524288)
    p.add_argument('--width', type=int, default=4096)
    p.add_argument('--rss-limit-mib', type=int, default=256)
    p.add_argument('--worker', choices=('build', 'query'))
    a = p.parse_args()
    if min(a.updates, a.width, a.rss_limit_mib) <= 0:
        p.error('counts and memory limit must be positive')
    source, saved = a.directory / 'large.vcd', a.directory / 'large.rvwi'
    if a.worker:
        from rvw.wave import index, ops
        start = time.monotonic()
        if a.worker == 'build':
            result = index.build(str(source), str(saved))
        else:
            result = ops.changes(str(saved), 'data', a.updates - 10, a.updates - 1)
            assert len(result) == 10
            for row in result:
                assert row['value'] == (hex((1 << a.width) - 1) if row['time'] % 2 else '0x0')
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_bytes = rss if sys.platform == 'darwin' else rss * 1024
        print(json.dumps(dict(operation=a.worker, wall_s=time.monotonic() - start,
                             peak_rss_bytes=rss_bytes, limit_bytes=a.rss_limit_mib * 2**20,
                             within_measured_limit=rss_bytes <= a.rss_limit_mib * 2**20)))
        return 0 if rss_bytes <= a.rss_limit_mib * 2**20 else 1
    if a.width % 4:
        p.error('width must be a multiple of four')
    a.directory.mkdir(parents=True, exist_ok=False)
    with source.open('w') as f:
        f.write(f'$timescale 1ns $end\n$scope module top $end\n$var wire {a.width} ! data $end\n'
                '$upscope $end\n$enddefinitions $end\n')
        values = ['0' * a.width, '1' * a.width]
        for t in range(a.updates):
            f.write(f'#{t}\nb{values[t % 2]} !\n')
    print(json.dumps(dict(source_bytes=source.stat().st_size, updates=a.updates, width=a.width)), flush=True)
    for worker in ('build', 'query'):
        subprocess.run([sys.executable, __file__, str(a.directory), '--updates', str(a.updates),
                        '--width', str(a.width), '--rss-limit-mib', str(a.rss_limit_mib),
                        '--worker', worker], check=True)
    print(json.dumps(dict(index_bytes=saved.stat().st_size)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
