"""Create a byte-addressed fetch feed from a RISC-V ELF reference image."""
from hashlib import sha256
import json
from pathlib import Path
from rvw.cosim.elf import Elf


def generate(elf,out,word_bytes=4):
    if word_bytes not in (4,8):raise ValueError('word_bytes must be 4 or 8')
    image=Elf(elf);memory={}
    for base,data,_ in image.segments:
        memory.update((base+i,b) for i,b in enumerate(data))
    addresses=sorted({a//word_bytes*word_bytes for a in memory})
    result={'schema':'rvw.instruction-feed/1','word_bytes':word_bytes,
        'reference_elf_sha256':sha256(image.data).hexdigest(),
        'words':[{'address':hex(a),'data':hex(int.from_bytes(bytes(memory.get(a+i,0) for i in range(word_bytes)),'little'))}
                 for a in addresses]}
    path=Path(out)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:stream.write(json.dumps(result,indent=2)+'\n')
    return {'schema':'rvw.instruction-feed-build/1','status':'generated','words':len(addresses),
        'word_bytes':word_bytes,'reference_elf_sha256':result['reference_elf_sha256'],
        'feed_sha256':sha256(path.read_bytes()).hexdigest(),
        'scope':'ELF load bytes only; unlisted fetch addresses fault; generation earns no execution credit'}
