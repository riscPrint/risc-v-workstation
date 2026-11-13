import copy
import json
import pytest
from rvw.formal.csr import load, step, generate


def model():
    return {'schema': 'rvw.csr/1', 'xlen': 32, 'csrs': [
        {'name': 'scratch', 'address': 0x340, 'reset': 5, 'privilege': 'M',
         'assembly_safe': True, 'fields': [
             {'lsb': 0, 'width': 4, 'access': dict(U='RO', S='RO', M='RW')},
             {'lsb': 4, 'width': 28, 'access': dict(U='WPRI', S='WPRI', M='WPRI')}]}]}


def txn(**kw):
    return dict(dict(privilege=3, read=False, write=True, data=0), **kw)


def test_mask_trap_and_hardware_priority():
    c = model()['csrs'][0]
    assert step(c, 0xA5, txn(data=0xFFFFFFFF), 32) == (False, 0xAF)
    assert step(c, 0xA5, txn(privilege=1, data=0), 32) == (True, 0xA5)
    assert step(c, 0xA5, txn(data=0, hw_clear=0x20, hw_set=2), 32) == (False, 0x82)
    c['present'] = False
    assert step(c, 5, txn(), 32) == (True, 5)


def test_legalization_and_side_effects():
    c = model()['csrs'][0]
    f = c['fields'][0]
    f.update(access=dict(U='RO', S='RO', M='WARL'), legal=[1, 5], legalize={15: 1})
    assert step(c, 5, txn(data=15), 32) == (False, 1)
    assert step(c, 5, txn(data=2), 32) == (False, 5)
    f['access']['M'] = 'WLRL'
    assert step(c, 5, txn(data=2), 32) == (True, 5)
    f['access']['M'] = 'RW'
    f['effect'] = 'w1c'
    assert step(c, 5, txn(data=1), 32) == (False, 4)
    f['effect'] = 'read_clear'
    assert step(c, 5, txn(read=True, write=False), 32) == (False, 0)
    assert step(c, 5, txn(read=True, data=2), 32) == (False, 2)


def test_generate(tmp_path):
    p = tmp_path/'model.json'
    p.write_text(json.dumps(model()))
    out = tmp_path/'generated'
    assert generate(p, out)['status'] == 'generated'
    sv = (out/'csr.sv').read_text()
    assert 'assert(trap == denied_scratch)' in sv
    assert "expected_scratch <= 32'd5" in sv
    assert 'state_scratch == expected_scratch' in sv
    assert 'csrw 0x340' in (out/'scratch.S').read_text()
    assert json.loads((out/'coverage.json').read_text())['groups'][0]['domains'][0] == ['0x340']
    with pytest.raises(FileExistsError):
        generate(p, out)


@pytest.mark.parametrize('fault', ['overlap', 'legal', 'reset', 'access', 'duplicate'])
def test_reject_bad_models(tmp_path, fault):
    m = model()
    c = m['csrs'][0]
    if fault == 'overlap': c['fields'][1]['lsb'] = 0
    if fault == 'legal': c['fields'][0]['access']['M'] = 'WARL'
    if fault == 'reset': c['reset'] = -1
    if fault == 'access': c['fields'][0]['access']['M'] = 'invented'
    if fault == 'duplicate': m['csrs'].append(copy.deepcopy(c))
    p = tmp_path/'m.json'
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError): load(p)


@pytest.mark.parametrize('mutation', ['none', 'wrong_mask', 'missing_trap', 'wrong_reset', 'writable_ro'])
def test_native_monitor_mutants(tmp_path, mutation):
    import shutil
    import subprocess
    from rvw.formal.csr import monitor
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus is not installed')
    m = model()
    (tmp_path/'model.json').write_text(json.dumps(m))
    (tmp_path/'csr.sv').write_text(monitor(load(tmp_path/'model.json')))
    reset_value = 0 if mutation == 'wrong_reset' else 5
    data_value = 0xFFFFFFFF if mutation == 'wrong_mask' else 15
    trap_value = 0 if mutation == 'missing_trap' else 1
    # Writable-RO fault changes a preserved bit in the independent observed state.
    if mutation == 'writable_ro': data_value = 31
    tb = f'''module tb;
reg clk=0; always #5 clk=~clk;
reg reset=1, valid=0, rd=0, wr=0, trap=0;
reg [1:0] privilege=3;
reg [11:0] address=12'h340;
reg [31:0] data=0, rdata=0, hw_set=0, hw_clear=0, state_scratch=0;
rvw_csr dut(.*);
initial begin
 #11; reset=0; state_scratch=32'd{reset_value};
 #10; valid=1; wr=1; data=32'hffffffff;
 #10; valid=0; state_scratch=32'd{data_value};
 #10; privilege=1; valid=1; trap={trap_value};
 #10; valid=0;
 #10; $finish;
end
endmodule'''
    (tmp_path/'tb.sv').write_text(tb)
    built = subprocess.run(['iverilog', '-g2012', '-s', 'tb', '-o', str(tmp_path/'sim'),
                            str(tmp_path/'csr.sv'), str(tmp_path/'tb.sv')], capture_output=True, text=True, timeout=15)
    assert built.returncode == 0, built.stderr
    run = subprocess.run(['vvp', str(tmp_path/'sim')], capture_output=True, text=True, timeout=15)
    assert ('ERROR:' in run.stdout) == (mutation != 'none'), run.stdout + run.stderr


def test_assembly_accounts_for_read_clear():
    from rvw.formal.csr import assembly
    c = model()['csrs'][0]
    c['fields'][0].update(access=dict(U='RO', S='RO', M='RO'), effect='read_clear')
    text = assembly(c, 32)
    assert 'li t0, 5\nbne s2, t0, fail' in text
    assert text.count('csrr t1, 0x340\nli t0, 0\nbne t1, t0, fail') == 3


def test_native_assembly_build(tmp_path):
    import shutil
    from pathlib import Path
    from rvw.formal.csr import assembly
    from rvw.common.proc import run_group
    compiler = shutil.which('riscv64-unknown-elf-gcc')
    if not compiler:
        path = Path('/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc')
        compiler = str(path) if path.is_file() else None
    if not compiler:
        pytest.skip('RISC-V GCC is not installed')
    c = model()['csrs'][0]
    c['fields'][1]['width'] = 60
    source = tmp_path/'csr.S'
    source.write_text(assembly(c, 64))
    result = run_group([compiler, '-march=rv64im_zicsr', '-mabi=lp64', '-nostdlib',
                        '-nostartfiles', '-Wl,-Ttext=0x80000000', str(source), '-o', str(tmp_path/'csr.elf')],
                       capture=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unknown_reset_requires_full_write_and_initializes_assembly(tmp_path):
    m = model()
    c = m['csrs'][0]
    c['reset_known'] = False
    p = tmp_path/'model.json'
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError, match='full-width'):
        load(p)
    c['fields'] = [dict(lsb=0, width=32, access=dict(U='RO', S='RO', M='RW'))]
    p.write_text(json.dumps(m))
    generate(p, tmp_path/'out')
    asm = (tmp_path/'out/scratch.S').read_text()
    assert asm.index('csrw 0x340, t0') < asm.index('csrr s2, 0x340')
    assert 'known_scratch' in (tmp_path/'out/csr.sv').read_text()
