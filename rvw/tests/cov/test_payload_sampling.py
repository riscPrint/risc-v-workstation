from hashlib import sha256
import json
import pytest
from rvw.cov.functional import functional


def test_payload_excludes_setup_and_breaks_dependency_history(tmp_path):
    path = tmp_path/'trace.jsonl'
    header = dict(schema='rvw.rvfi/1',xlen=32,isa='rv32i',elf_sha256='a'*64)
    rows = [dict(order=i,insn='0x00100093',mode=3,rd=1,rs1_rdata='0x0',rs2_rdata='0x0',pc=hex(256+4*i)) for i in range(3)]
    path.write_text('\n'.join(json.dumps(r) for r in [header,*rows])+'\n')
    key = sha256(path.read_bytes()).hexdigest()
    region = {'elf_sha256':'a'*64,'policy':'payload-pc-v1','ranges':[[260,264]]}
    full = functional([path])
    filtered = functional([path],payload_regions={key:region})
    assert full['retired'] == 3 and filtered['retired'] == 1
    assert full['config_sha256'] != filtered['config_sha256']
    assert filtered['traces'][key]['payload_region'] == region
    region['elf_sha256'] = 'b'*64
    with pytest.raises(ValueError,match='trace ELF'):
        functional([path],payload_regions={key:region})
