"""Uniform integer payloads for a measured random control arm."""
from hashlib import sha256
import json
from pathlib import Path
import random

from . import captured
from .isa import plan, extensions
from .stimulus import R_TYPE, I_TYPE


@captured.command
def generate(manifest, source_root, work_dir, registers, seed):
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('seed must be uint32')
    if (not isinstance(registers, list) or len(registers) != 3 or len(set(registers)) != 3
            or any(type(r) is not int or not 1 <= r <= 31 for r in registers)):
        raise ValueError('registers must declare three distinct writable integer registers')
    pinned = plan(manifest, source_root)
    xlen, _ = extensions(pinned['isa_plan']['manifest']['isa'])
    rng = random.Random(seed)
    name = rng.choice(R_TYPE + I_TYPE)
    record = next(i for i in pinned['isa_plan']['instructions'] if i['name'] == name)
    rd, rs1, rs2 = registers
    a, b, imm = rng.getrandbits(xlen), rng.getrandbits(xlen), rng.getrandbits(12)
    word = record['value'] | rd << 7 | rs1 << 15
    word |= rs2 << 20 if name in R_TYPE else imm << 20
    source = ('.option norvc\n.option norelax\n'
              f'li x{rs1}, 0x{a:x}\nli x{rs2}, 0x{b:x}\n'
              '.global rvw_payload_start, rvw_payload_end\nrvw_payload_start:\n'
              f'.word 0x{word:08x}\nrvw_payload_end:\n')
    directory = Path(work_dir)
    directory.mkdir(parents=True, exist_ok=False)
    path = directory/'payload.S'
    path.write_text(source)
    result = dict(schema='rvw.stimulus-candidate/1', status='generated', goal='random', seed=seed,
                  profile='uniform-integer-control', xlen=xlen, registers=registers,
                  model=dict(instruction=word, rs1=a, rs2=b, imm12=imm),
                  source=str(path), source_sha256=sha256(source.encode()).hexdigest(),
                  measured_hits=[], reason='unexecuted random control candidate')
    (directory/'candidate.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
