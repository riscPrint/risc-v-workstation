"""NOP reduction of sized code symbols in captured per-hart ELF inputs."""
import copy
import hashlib
import json
from pathlib import Path
from ..runs.elf import Elf
from .streams import instruction_slots


def reduce_hart_instructions(reducer):
    selections=reducer.o.hart_symbols
    if not selections:raise ValueError('hart_instructions needs --hart-symbol HART:NAME')
    base=reducer.best['cmd']
    source=base.get('hart_images')
    if not source:raise ValueError('hart_instructions needs --hart-images')
    source=Path(source)
    if not source.is_absolute():source=reducer.inputs.root/source
    captured=reducer.inputs.capture.file(source)
    data=json.loads(captured.copy.read_text())
    if data.get('schema')!='rvw.hart-images/1':raise ValueError('expected rvw.hart-images/1')
    rows=data.get('harts',[])
    ids=[r.get('hart') for r in rows]
    if len(ids)<2 or any(type(h) is not int or h<0 for h in ids) or len(set(ids))!=len(ids):
        raise ValueError('invalid hart inventory')
    expected={r['hart']:r['elf_sha256'] for r in reducer.run.get('details',{}).get('hart_images',[])}
    if expected!={r['hart']:r['elf_sha256'] for r in rows}:
        raise ValueError('hart images differ from original C1 identities')
    for row in rows:
        path=Path(row['elf'])
        if not path.is_absolute():path=source.parent/path
        item=reducer.inputs.capture.file(path)
        if item.sha256!=row['elf_sha256']:raise ValueError('hart ELF digest differs')
        row['elf']=str(item.copy)
    manifest=reducer.out/'hart-inputs.json'
    manifest.write_text(json.dumps(data)+'\n')
    saved=reducer.inputs.capture.file(manifest)
    reducer.best['cmd']=base.set(hart_images=str(saved.copy))
    for selection in selections:
        hart_text,sep,name=selection.partition(':')
        if not sep or not hart_text.isdecimal() or not name:raise ValueError('expected HART:NAME')
        hart=int(hart_text)
        base=reducer.best['cmd']
        data=json.loads(Path(base.get('hart_images')).read_text())
        row=next((r for r in data['harts'] if r['hart']==hart),None)
        if row is None:raise ValueError('selected hart is absent')
        original=Elf(row['elf']);slots=instruction_slots(original,name)
        primary=(hart==min(ids) and hashlib.sha256(Path(base.get('elf')).read_bytes()).hexdigest()==row['elf_sha256'])
        def command(kept):
            image=Elf(row['elf']);keep=set(kept)
            for i,(offset,size) in enumerate(slots):
                if i not in keep:image.data[offset:offset+size]=bytes.fromhex('0100' if size==2 else '13000000')
            path=reducer.out/f'hart-{hart}-{len(reducer.trials)}.elf';image.save(str(path))
            item=reducer.inputs.capture.file(path)
            candidate=copy.deepcopy(data)
            selected=next(r for r in candidate['harts'] if r['hart']==hart)
            selected.update(elf=str(item.copy),elf_sha256=item.sha256)
            manifest=reducer.out/f'harts-{len(reducer.trials)}.json'
            manifest.write_text(json.dumps(candidate)+'\n')
            saved=reducer.inputs.capture.file(manifest)
            elf=str(item.copy) if primary else reducer.best['elf']
            return base.set(hart_images=str(saved.copy),elf=elf),dict(elf=elf,hart=hart,instructions_kept=kept)
        reducer._stream_search('hart:'+selection,range(len(slots)),command)
