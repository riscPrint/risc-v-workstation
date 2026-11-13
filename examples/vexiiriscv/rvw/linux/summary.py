"""Summarize one contiguous boot history without mixing slice and total time."""
import argparse
import json
import math
from pathlib import Path


def summarize(paths):
    rows = sorted((json.loads(Path(p).read_text()) for p in paths), key=lambda r: int(r['cycle']))
    if not rows:
        raise ValueError('no slice reports')
    cycle = retired = 0
    wall = 0.0
    for row in rows:
        if row['schema'] != 'rvw.vexii-boot-slice-result/1':
            raise ValueError('expected boot-slice reports')
        if (cycle+int(row['slice_cycles']) != int(row['cycle'])
                or retired+int(row['slice_retired']) != int(row['retired'])):
            raise ValueError('reports are not one contiguous history from reset')
        seconds = row['wall_seconds']
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('slice wall time must be finite and positive')
        cycle, retired = int(row['cycle']), int(row['retired'])
        wall += seconds
    last = rows[-1]
    marker = any('RVW_LINUX_USERSPACE\n' in text.replace('\r\n','\n') for text in last['console'].values())
    return dict(slices=len(rows), cycles=cycle, retired=retired, wall_seconds=wall,
                cycles_per_second=cycle/wall, instructions_per_second=retired/wall,
                status=last['status'], userspace_marker=marker,
                user_retirements=int(last['retired_by_mode'][0]) if 'retired_by_mode' in last else 'not recorded')


if __name__ == '__main__':
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('reports', type=Path, nargs='+')
    args = p.parse_args()
    print('| Metric | Value |\n|---|---:|')
    for key, value in summarize(args.reports).items():
        print(f'| {key} | {value:.3f} |' if isinstance(value,float) else f'| {key} | {value} |')
