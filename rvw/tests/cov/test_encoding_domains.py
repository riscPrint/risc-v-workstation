import pytest
from .test_functional import decoded_observations_only
from rvw.cov.encoding_domains import domain


@pytest.mark.parametrize('name',['rd','rs1','rs2','rs3','rd_rs1_n0','vd','vs1','vs2','vs3'])
def test_scalar_fp_vector_and_alias_register_domains(name):
    assert domain(name,11,7)==list(range(32))


def test_small_fields_keep_unseen_and_reserved_encodings():
    assert domain('rm',14,12)==list(range(8))
    assert domain('rd_p',4,2)==list(range(8))
    assert domain('vm',25,25)==[0,1]
    assert domain('nf',31,29)==list(range(8))
    assert domain('imm20',31,12) is None
    assert domain('csr',31,20) is None


def test_pinned_vector_fields_use_full_expected_domains(tmp_path):
    import json
    from hashlib import sha256
    from rvw.cov.functional import functional
    files={'extensions/rv_v':'vadd.vv vd vs1 vs2 vm 31..26=0 14..12=0 6..2=0x15 1..0=3\n',
           'arg_lut.csv':'"vd",11,7\n"vs1",19,15\n"vs2",24,20\n"vm",25,25\n'}
    for name,text in files.items():
        path=tmp_path/name;path.parent.mkdir(exist_ok=True);path.write_text(text)
    manifest={'schema':'rvw.isa/1','isa':'rv32iv','extensions':{'i':{'version':'2.1'},'v':{'version':'1.0'}},
              'options':{},'source':{'revision':'a'*40,'files':{k:sha256(v.encode()).hexdigest() for k,v in files.items()}}}
    config=tmp_path/'isa.json';config.write_text(json.dumps(manifest))
    word=0x57 | 3<<7 | 1<<15 | 2<<20 | 1<<25
    trace=tmp_path/'trace.jsonl'
    trace.write_text(json.dumps({'schema':'rvw.rvfi/1','xlen':32,'isa':'rv32iv'})+'\n'+
                     json.dumps({'order':0,'insn':hex(word),'rd':0,'mode':3})+'\n')
    report=functional([trace],manifest=config,source_root=tmp_path)
    assert report['groups']['isa_vadd.vv_vd']['expected_bins']==32
    assert report['groups']['isa_vadd.vv_vd']['hits']==[{'bin':[3],'count':1}]
    assert report['groups']['isa_vadd.vv_vm']['holes']==[[0]]
