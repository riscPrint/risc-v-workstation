"""Project declarations replace architectural upstream preset values."""
import json
from types import SimpleNamespace
import pytest
from rvw.regress.dv_target import derive, apply

pytestmark = pytest.mark.fast


def inputs(tmp_path):
    platform = tmp_path/'platform.json'
    platform.write_text(json.dumps(dict(xlen=32, isa='rv32im_zicsr', privilege_modes='M',
        reset_pc='0x80000000', ram=[dict(base='0x80000000', size='0x10000')], aligned_mem=True)))
    csrs = tmp_path/'csrs.json'
    csrs.write_text(json.dumps(dict(schema='rvw.csr-selection/1', xlen=32, csrs=[
        dict(name='mscratch', reset=0, reset_known=False, fields=[dict(name='SCRATCH')]),
        dict(name='sscratch', reset=0, present=False)])))
    return platform, csrs


def test_derivation_uses_catalog_and_preserves_unknown_reset(tmp_path):
    p, c = inputs(tmp_path)
    target = derive(p, c)
    assert target['csrs'][0]['address'] == 0x340
    assert target['csrs'][0]['reset_known'] is False
    assert len(target['csrs']) == 1
    assert target['reset_pc'] == 0x80000000
    enum = lambda **kw: SimpleNamespace(**kw)
    package = enum(riscv_instr_group_t=enum(RV32I='I', RV32M='M'),
        privileged_mode_t=enum(MACHINE_MODE='M'), privileged_reg_t=enum(MSCRATCH=0x340),
        satp_mode_t=enum(BARE='bare'), mtvec_mode_t=enum(DIRECT='direct'))
    module = SimpleNamespace(supported_isa=['I', 'M', 'C'], implemented_csr=['SATP'])
    apply(target, module, package)
    assert module.supported_isa == ['I', 'M']
    assert module.implemented_csr == [0x340]
    assert module.support_unaligned_load_store == 0
    assert module.supported_privileged_mode == ['M']


@pytest.mark.parametrize('change,message', [({'xlen':64}, 'XLEN'),
    ({'privilege_modes':'S'}, 'privilege'), ({'reset_pc':'0x1000'}, 'RAM'),
    ({'isa':'rv32if'}, 'requires')])
def test_inconsistent_project_refused(tmp_path, change, message):
    p,c=inputs(tmp_path)
    data=json.loads(p.read_text()); data.update(change); p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=message):
        derive(p,c)


def test_rv64_keeps_base_rv32_instruction_groups(tmp_path):
    p,c=inputs(tmp_path)
    data=json.loads(p.read_text()); data.update(xlen=64, isa='rv64im_zicsr'); p.write_text(json.dumps(data))
    data=json.loads(c.read_text()); data['xlen']=64; c.write_text(json.dumps(data))
    target=derive(p,c)
    enum=lambda **kw: SimpleNamespace(**kw)
    package=enum(riscv_instr_group_t=enum(RV32I='32I', RV32M='32M', RV64I='64I', RV64M='64M'),
        privileged_mode_t=enum(MACHINE_MODE='M'), privileged_reg_t=enum(MSCRATCH=0x340),
        satp_mode_t=enum(BARE='bare'), mtvec_mode_t=enum(DIRECT='direct'))
    module=SimpleNamespace()
    apply(target,module,package)
    assert module.supported_isa == ['32I','32M','64I','64M']


def test_misaligned_policy_comes_from_declared_trap_behavior(tmp_path):
    p,c=inputs(tmp_path)
    data=json.loads(p.read_text())
    data.update(aligned_mem=False, misaligned=dict(load='trap', store='trap'))
    p.write_text(json.dumps(data))
    assert derive(p,c)['unaligned_load_store'] is False
    data['misaligned']=dict(load='emulate', store='emulate')
    p.write_text(json.dumps(data))
    assert derive(p,c)['unaligned_load_store'] is True
