import json
import shutil
from pathlib import Path
import pytest
from rvw.common.proc import run_group
from rvw.formal.csr_bank import load,step,generate


def model():
    return dict(schema='rvw.csr-bank/1',xlen=32,modes=['M','S','U'],setup=['enable_fpu','open_pmp'],
      banks=[dict(name='fp',width=8,reset=0),dict(name='machine',width=32,reset=0),dict(name='supervisor',width=32,reset=0)],
      views=[dict(name='fcsr',catalog='fcsr',bank='fp',mask=255,write_mask=255),
             dict(name='fflags',catalog='fflags',bank='fp',mask=31,write_mask=31),
             dict(name='frm',catalog='frm',bank='fp',shift=5,mask=7,write_mask=7),
             dict(name='mscratch',catalog='mscratch',bank='machine',mask=0xffffffff,write_mask=0xffffffff),
             dict(name='sscratch',catalog='sscratch',bank='supervisor',mask=0xffffffff,write_mask=0xffffffff)],
      sequences=[dict(name='aliases',accesses=[dict(view='fcsr',op='write',data=0),dict(view='frm',op='write',data=2),
            dict(view='fcsr',op='read'),dict(view='fflags',op='set',data=3),dict(view='fcsr',op='read'),
            dict(view='fflags',op='clear',data=1),dict(view='fcsr',op='read')]),
          dict(name='privilege',accesses=[dict(view='mscratch',op='write',data=37),
            dict(view='mscratch',op='read',privilege='U'),dict(view='mscratch',op='read',privilege='S'),
            dict(view='sscratch',op='write',data=51,privilege='S'),dict(view='sscratch',op='read',privilege='U'),
            dict(view='sscratch',op='read'),dict(view='fcsr',op='write',data=99,privilege='U'),dict(view='frm',op='read')])])


def write_model(tmp_path):
    p=tmp_path/'model.json';p.write_text(json.dumps(model()));return p


def test_shared_storage_and_permissions(tmp_path):
    obj=load(write_model(tmp_path));state={b['name']:b['reset'] for b in obj['banks']}
    result=step(obj,state,dict(view='frm',op='write',data=2))
    assert result['state']['fp']==64
    assert step(obj,result['state'],dict(view='fcsr',op='read'))['rdata']==64
    denied=step(obj,state,dict(view='mscratch',op='write',data=7,privilege='U'))
    assert denied['trap'] and denied['state']==state
    result=generate(write_model(tmp_path),tmp_path/'out')
    assert result['banks']==3 and result['sequences']==['aliases','privilege']
    assert 'mret' in (tmp_path/'out/privilege.S').read_text()


@pytest.mark.parametrize('mutation',['shift','mask','policy','mode'])
def test_invalid_alias_models(tmp_path,mutation):
    obj=model()
    if mutation=='shift': obj['views'][2]['shift']=8
    if mutation=='mask': obj['views'][2]['write_mask']=255
    if mutation=='policy': obj['views'][2]['warl']='ignored'
    if mutation=='mode': obj['modes']=['M']
    p=tmp_path/'bad.json';p.write_text(json.dumps(obj))
    with pytest.raises(ValueError):load(p)


@pytest.mark.slow
@pytest.mark.parametrize('name',['aliases','privilege'])
@pytest.mark.parametrize('mutant',[False,True])
def test_spike_alias_privilege_sequences(tmp_path,name,mutant):
    gcc=shutil.which('riscv64-unknown-elf-gcc')
    if not gcc:
        path=Path('/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc')
        gcc=str(path) if path.is_file() else None
    spike=shutil.which('spike')
    if not gcc or not spike: pytest.skip('RISC-V GCC and Spike required')
    generate(write_model(tmp_path),tmp_path/'out')
    source=tmp_path/'out'/(name+'.S')
    if mutant:
        text=source.read_text()
        needle='li t0, 64\nbne s2, t0, fail' if name=='aliases' else 'li t0, 51\nbne s2, t0, fail'
        assert needle in text
        source.write_text(text.replace(needle,'li t0, 65\nbne s2, t0, fail',1))
    root=Path(__file__).resolve().parents[2]
    elf=tmp_path/name
    build=run_group([gcc,'-march=rv32imafdc_zicsr','-mabi=ilp32','-nostdlib','-nostartfiles',
        '-T',str(root/'examples/vexriscv/rvw/programs/link.ld'),str(source),'-o',str(elf)],capture=True,timeout=20)
    assert build.returncode==0,build.stdout+build.stderr
    run=run_group(['nice','-n','10',spike,'--isa=rv32imafdc_zicsr_zifencei','--priv=msu',str(elf)],capture=True,timeout=20)
    assert not run.timed_out,run.stdout+run.stderr
    assert run.returncode==(1 if mutant else 0),run.stdout+run.stderr


def test_existing_csr_generator_dispatch_and_coverage(tmp_path):
    from rvw.formal.csr import generate as public_generate
    result=public_generate(write_model(tmp_path),tmp_path/'out')
    assert result['banks']==3
    assert len(json.loads((tmp_path/'out/coverage.json').read_text())['groups'])==5


def test_sequence_trap_control_is_not_an_untracked_bank(tmp_path):
    obj=model();obj['views'][3].pop('catalog')
    obj['views'][3].update(address=0x305,privilege='M')
    p=tmp_path/'bad.json';p.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='custom execution harness'):load(p)
