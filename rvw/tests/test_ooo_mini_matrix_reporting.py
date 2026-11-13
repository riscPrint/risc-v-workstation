"""An absent RTL sample must never become a measured zero delta."""
import importlib.util
import json
from hashlib import sha256
from pathlib import Path
import pytest
from rvw.ooo.core import run

pytestmark = pytest.mark.fast


def test_missing_variant_stays_inconclusive(tmp_path, monkeypatch):
    folder=Path(__file__).resolve().parents[2]/'examples/ooo-mini/rvw/arch'
    monkeypatch.syspath_prepend(str(folder))
    spec=importlib.util.spec_from_file_location('mini_score',folder/'score-matrix.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'PROGRAMS',('p',))
    monkeypatch.setattr(module,'TRAINING',('p',))
    monkeypatch.setattr(module,'VARIANTS',{'default':{},'small':{'rob_entries':4}})
    captures=tmp_path/'captures';directory=captures/'default/p';directory.mkdir(parents=True)
    header=dict(schema='rvw.rvfi/1',xlen=64,core='test',config='tiny',isa='rv64i',
                elf='test.elf',elf_sha256='e'*64,seed=1)
    rows=[header]
    for i in range(4):
        row={k:'0x0' for k in 'pc pc_next insn rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata'.split()}
        row.update({k:0 for k in 'order cycle mode rs1 rs2 rd mem_rmask mem_wmask'.split()})
        row.update({k:False for k in 'trap intr halt mem_fault'.split()})
        row.update(order=i,cycle=i,insn='0x13');rows.append(row)
    rows.append(dict(event='end',status='pass',instret=4,cycle=4))
    trace=directory/'rvfi.jsonl';trace.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    config=dict(fetch_width=2,fetch_entries=4,rename_width=2,rob_entries=8,issue_width=2,
                issue_entries=4,load_entries=2,store_entries=2,commit_width=2,latencies={'alu':1})
    output=tmp_path/'score';output.mkdir();cp=output/'default.json';cp.write_text(json.dumps(config))
    model=run(cp,trace)
    c1={k:header[k] for k in ('core','config','elf','elf_sha256','seed')}
    result=directory/'result.json';result.write_text(json.dumps(c1))
    hashes={f:sha256((directory/f).read_bytes()).hexdigest() for f in ('result.json','rvfi.jsonl')}
    (captures/'rtl-summary.json').write_text(json.dumps([dict(config='default',program='p',
        hashes=hashes,instret=4,ipc=model['ipc'])]))
    (output/'predictions.json').write_text(json.dumps(dict(base=config,candidates=[],chosen={},
        models={'default/p':model,'small/p':model},base_hashes={'p':hashes})))
    module.main(captures,output)
    assert not (output/'model-summary.json').exists()
    module.main(captures,output,'--allow-incomplete')
    partial=json.loads((output/'partial-model-summary.json').read_text())
    assert partial['status']=='inconclusive'
    assert partial['missing_captures']==[dict(config='small',program='p')]
    assert partial['rows']==[]
    assert partial['scored_pairs']==0
    assert not (output/'model-summary.json').exists()
