import pytest
from rvw.formal.isa_memory import render

pytestmark = pytest.mark.fast


def config():
    return dict(depth=6, memory=dict(protocol='combinational-byte', response_cycles=0,
        initial='symbolic-stable', reads=[dict(address='ia', data='id', mask='im'),
                                         dict(address='da', data='dd', mask='dm')],
        writes=[dict(address='wa', data='wd', mask='wm')]))


def test_memory_tracks_reads_then_writes_without_restricting_requests():
    text = render(config())
    assert 'h<7' in text
    assert 'assert(rvw_mem_count < 7)' in text
    assert 'rvw_mem_2_data[h][24 +: 8]' in text
    assert text.index('rvw_mem_0_data[h]') < text.index('rvw_mem_2_data[h]')
    assert "assume(dd[0 +: 8] == id[0 +: 8])" in text
    assert 'assume(wa' not in text
    assert 'assume(wm' not in text


@pytest.mark.parametrize('field,value', [('protocol','axi'), ('initial','zero'), ('response_cycles',1)])
def test_refuse_unimplemented_memory_semantics(field, value):
    cfg = config()
    cfg['memory'][field] = value
    with pytest.raises(ValueError):
        render(cfg)


def test_missing_contract_preserves_wrapper():
    assert render(dict(depth=6)) == ''


def test_reject_expression_in_bus_binding():
    cfg = config()
    cfg['memory']['reads'][0]['address'] = 'dut.address'
    with pytest.raises(ValueError, match='identifiers'):
        render(cfg)


def test_prepare_inserts_environment_and_hashes_it(tmp_path):
    from rvw.formal.riscv import prepare, FIELDS
    root = tmp_path / 'rf'
    (root / 'checks').mkdir(parents=True)
    (root / 'insns').mkdir()
    wrapper = tmp_path / 'wrapper.sv'
    wrapper.write_text('module rvfi_wrapper; @RVFI_CONNECTIONS@\n@MEMORY_ENVIRONMENT@\nendmodule')
    rtl = tmp_path / 'rtl.v'
    rtl.write_text('module core; endmodule')
    cfg = config() | dict(root=str(root), wrapper=str(wrapper), verilog=[str(rtl)],
        isa='rv32i', nret=1, solver='yices', checks=['insn_lw_ch0', 'cover'],
        ports={f: 'io_' + f for f in FIELDS + ['mem_fault', 'mem_fault_rmask', 'mem_fault_wmask']})
    core, identity = prepare(cfg, tmp_path / 'out')
    generated = (core / 'wrapper.sv').read_text()
    assert '@MEMORY_ENVIRONMENT@' not in generated
    assert 'assume(dd' in generated
    assert '@MEMORY_ENVIRONMENT@' in wrapper.read_text()
    assert identity[str(wrapper)]
    assert '.io_mem_fault (rvfi_mem_fault)' in generated
    assert '`define RISCV_FORMAL_MEM_FAULT' in (core / 'checks.cfg').read_text()
