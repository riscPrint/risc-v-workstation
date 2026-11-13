#!/usr/bin/env python3
"""Print dependency arguments for a pinned, external Berkeley SoftFloat tree.

Run: python softfloat.py ROOT f32_add. Add the printed arguments to datapath.
This writes one platform header under ROOT/rvw-platform, outside this repo.
"""
import argparse
from pathlib import Path
import re
import shlex
import subprocess

REVISION = '07ebd29db0cfb55723a79fbbffe99103ef38e305'


def prepare(root, operation):
    root = Path(root).resolve()
    revision = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
    if revision != REVISION:
        raise ValueError('SoftFloat revision must be '+REVISION)
    platform = root/'rvw-platform'
    platform.mkdir(exist_ok=True)
    (platform/'platform.h').write_text('#define LITTLEENDIAN 1\n#define SOFTFLOAT_FAST_INT64 1\n#define INLINE static inline\n')
    files = {p.stem:p for p in (root/'source').glob('*.c')}
    files.update({p.stem:p for p in (root/'source/RISCV').glob('*.c')})
    if operation not in files:
        raise ValueError('unknown SoftFloat operation')
    selected = {files['softfloat_state']}
    # RISC-V NaN conversion macros call this from specialize.h.
    # A scan of C source tokens alone does not see the macro body.
    pending = [files[operation], files['softfloat_raiseFlags']]
    # SoftFloat splits tables from the functions that use them.
    pending += list((root/'source').glob('s_*_1Ks.c'))
    while pending:
        file = pending.pop()
        if file in selected:
            continue
        selected.add(file)
        for symbol in set(re.findall(r'\b[A-Za-z_]\w*\b',file.read_text())):
            name = 's_'+symbol[len('softfloat_'):] if symbol.startswith('softfloat_') else symbol
            target = files.get(name) or files.get(symbol)
            if target and target not in selected:
                pending.append(target)
    argv = ['--reference-tree',str(root)]
    for directory in ('rvw-platform','source/include','source/RISCV'):
        argv += ['--reference-include', directory]
    for file in sorted(selected):
        argv += ['--reference-source',str(file.relative_to(root))]
    return argv

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('root');p.add_argument('operation')
    a=p.parse_args()
    print(shlex.join(prepare(a.root,a.operation)))
