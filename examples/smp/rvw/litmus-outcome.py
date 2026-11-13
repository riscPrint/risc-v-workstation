#!/usr/bin/env python3
"""Read an existing native capture for the pinned litmus outcome checker."""
import hashlib
import json
import os
from pathlib import Path
import sys
from rvw.cosim.trace import Trace
from rvw.results import load_run
from rvw.runs.elf import Elf
from litmus_programs import parse


def outcome(test):
    _,_,projection,digest=parse(test)
    base=Path(os.environ.get('RVW_SMP_LITMUS_OUT',Path(__file__).parent/'out/litmus'))
    root=base/Path(test).stem
    run=root.with_name(root.name+'-run')
    metadata=json.loads((root/'litmus.json').read_text())
    if metadata['test_sha256']!=digest or metadata['projection']!=projection:
        raise ValueError('capture input differs from pinned test')
    c1=load_run(run/'result.json')
    if c1.status!='pass' or c1.why_inconclusive:
        raise ValueError('passing C1 result required')
    manifest=json.loads((root/'hart-images.json').read_text())
    elfs={r['hart']:Elf(r['elf']) for r in manifest['harts']}
    hashes={r['hart']:r['elf_sha256'] for r in manifest['harts']}
    if any(hashlib.sha256(e.data).hexdigest()!=hashes[h] for h,e in elfs.items()):
        raise ValueError('captured ELF changed')
    reader=Trace(run/'rvfi.jsonl')
    registers={h:[0]*32 for h in elfs}; done={}
    try:
        if {r['hart']:r['elf_sha256'] for r in reader.header['hart_images']}!=hashes:
            raise ValueError('trace image hashes differ')
        for r in reader:
            h=r.get('hart')
            if r.get('event')=='hart_end':done[h]=r['status']
            elif 'event' not in r:
                offset=elfs[h].file_offset(r['pc'])
                if offset is None or int.from_bytes(elfs[h].data[offset:offset+4],'little')!=r['insn']:
                    raise ValueError('retired instruction differs from input')
                if r['rd']:registers[h][r['rd']]=r['rd_wdata']
        if done!={0:'pass',1:'pass'}:
            raise ValueError('both harts must complete')
    finally:reader.close()
    values={key:registers[int(key.split(':')[0])][int(key.split('x')[1])] for key in projection}
    return dict(harts=2,complete=True,observations=[dict(state=values,count=1)])


if __name__=='__main__':
    print(json.dumps(outcome(sys.argv[1])))
