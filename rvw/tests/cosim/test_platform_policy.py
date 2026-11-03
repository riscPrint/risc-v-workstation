"""Platform choices must change the reference, never mask a wrong trace value."""
import copy
import json
from pathlib import Path

import pytest
from rvw.cosim.platform import Platform
from rvw.cosim.sail_config import build_config
from cosim_build import _build
from model_fixtures import Spike
from test_lockstep import plain_trace, run_check


@pytest.mark.parametrize('key,value', [
    ('privilege_modes', 'MS'), ('privilege_modes', 'MSUH'),
    ('misaligned', {'load': 'anything'}),
    ('endianness', {'data': 'big'}), ('ecall_tval', 'any'),
    ('absent_pmp_csrs', 'ignore'), ('absent_pmp_csrs', 'read_zero_write_ignored'),
])
def test_refuse_unsupported_platform(tmp_path, key, value):
    config = json.loads((Path(__file__).parents[2] / 'src/rvw/cosim/configs/boom.json').read_text())
    config[key] = value
    path = tmp_path / 'platform.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        Platform.load('test', path)


def program(tmp_path_factory, body):
    source = tmp_path_factory.mktemp('policy-source') / 'policy.S'
    source.write_text('''.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
''' + body + '''
finish:
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.balign 4
handler:
  j finish
.section .data
.balign 8
buffer: .dword 0x123456789abcdef
.globl tohost
tohost: .dword 0
''')
    return _build(tmp_path_factory, source)


@pytest.mark.parametrize('modes,bits', [('M', 0), ('MU', 1 << 20), ('MSU', (1 << 20) | (1 << 18))])
def test_privilege_modes_reach_spike(tmp_path_factory, platform, modes, bits):
    elf = program(tmp_path_factory, 'csrr a0, misa')
    p = copy.deepcopy(platform)
    p.privilege_modes = modes
    model = Spike(p, elf)
    try:
        for _ in range(10):
            e = model.step()
            if e['rd'] == 10:
                assert e['rd_wdata'] & ((1 << 20) | (1 << 18)) == bits
                break
        else:
            pytest.fail('misa read not reached')
    finally:
        model.close()


@pytest.mark.parametrize('opcode,cause', [('lw a0, 1(t0)', 4), ('sw zero, 1(t0)', 6), ('amoadd.w a0, zero, (t0)', 6), ('lr.w a0, (t0)', 4), ('sc.w a0, zero, (t0)', 6)])
@pytest.mark.parametrize('policy', ['trap', 'emulate'])
def test_misaligned_outcome(tmp_path_factory, platform, opcode, cause, policy):
    atomic = opcode.startswith(('amo', 'lr.', 'sc.'))
    elf = program(tmp_path_factory, 'la t0, buffer\n' + ('addi t0, t0, 1\n' if atomic else '') + opcode)
    p = copy.deepcopy(platform)
    p.aligned_mem = False
    p.misaligned.update(load=policy, store=policy, atomic='trap' if policy == 'trap' else 'access_fault')
    model = Spike(p, elf)
    try:
        for _ in range(12):
            e = model.step()
            if e['insn'] & 0x7f in (3, 0x23, 0x2f):
                if policy == 'trap' or atomic:
                    assert e['trap'] and e['cause'] == ((5 if cause == 4 else 7) if atomic and policy == 'emulate' else cause)
                    assert e['tval'] == model.elf.symbols.get('buffer', 0) + 1
                else:
                    assert not e['trap']
                    assert e['mem_rmask'] or e['mem_wmask']
                break
        else:
            pytest.fail('memory operation not reached')
    finally:
        model.close()


def test_absent_pmp_zero_is_exact(tmp_path_factory, tmp_path, platform):
    elf = program(tmp_path_factory, 'li t0, -1\ncsrw pmpaddr0, t0\ncsrr a0, pmpaddr0\ncsrw pmpcfg0, t0\ncsrr a1, pmpcfg0')
    p = copy.deepcopy(platform)
    p.pmp_regions = 0
    p.absent_pmp_csrs = 'read_zero_write_ignored'
    rows = plain_trace(elf, p)
    reads = [r for r in rows if r.get('rd') in (10, 11)]
    assert len(reads) == 2 and all(int(r['rd_wdata'], 16) == 0 for r in reads)
    assert run_check(tmp_path, rows, elf, p)['status'] == 'match'
    reads[0]['rd_wdata'] = '0x1'
    assert run_check(tmp_path, rows, elf, p)['status'] == 'mismatch'
    reads[0]['rd_wdata'] = '0x0'
    p.absent_pmp_csrs = 'trap'
    assert run_check(tmp_path, rows, elf, p)['status'] == 'mismatch'


@pytest.mark.parametrize('value', [0, 0x73, 0x74])
def test_ecall_tval_is_exact(tmp_path, umode_elf, platform, value):
    p = copy.deepcopy(platform)
    p.ecall_tval = 'insn'
    rows = plain_trace(umode_elf, p)
    event = next(r for r in rows if r.get('event') == 'trap' and int(r['cause'], 16) == 8)
    event['tval'] = hex(value)
    result = run_check(tmp_path, rows, umode_elf, p)
    assert result['status'] == ('match' if value == 0x73 else 'mismatch')
    if value == 0x73:
        event['cause'] = '0x9'
        assert run_check(tmp_path, rows, umode_elf, p)['status'] == 'mismatch'


@pytest.mark.parametrize('key,value', [('privilege_modes', 'M'), ('ecall_tval', 'insn'), ('absent_pmp_csrs', 'read_zero_write_ignored')])
def test_sail_refuses_unimplemented_settings(platform, key, value):
    p = copy.deepcopy(platform)
    setattr(p, key, value)
    with pytest.raises(ValueError, match='Sail cannot implement'):
        build_config({}, p, [])


@pytest.mark.parametrize('field', ['instruction', 'data', 'page_table', 'device'])
def test_each_endian_domain_is_refused(tmp_path, field):
    config = json.loads((Path(__file__).parents[2] / 'src/rvw/cosim/configs/boom.json').read_text())
    config['endianness'][field] = 'big'
    path = tmp_path / 'platform.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='endianness'):
        Platform.load('test', path)


@pytest.mark.parametrize('offset', [7, 4095])
def test_split_completion_is_refused(tmp_path_factory, platform, offset):
    elf = program(tmp_path_factory, f'la t0, buffer\nli t1, {offset}\nadd t0, t0, t1\nlw a0, 0(t0)')
    p = copy.deepcopy(platform)
    p.aligned_mem = False
    p.misaligned.update(load='emulate', store='emulate', atomic='access_fault')
    model = Spike(p, elf)
    try:
        with pytest.raises(ValueError, match='multiple memory|split bus/page'):
            for _ in range(20):
                model.step()
    finally:
        model.close()


@pytest.mark.parametrize('csr', ['0x3a1', '0x3f0'])
def test_absent_pmp_setting_leaves_other_csrs_illegal(tmp_path_factory, platform, csr):
    elf = program(tmp_path_factory, f'csrr a0, {csr}')
    p = copy.deepcopy(platform)
    p.pmp_regions = 0
    p.absent_pmp_csrs = 'read_zero_write_ignored'
    model = Spike(p, elf)
    try:
        for _ in range(8):
            e = model.step()
            if e['trap']:
                assert e['cause'] == 2
                break
        else:
            pytest.fail('illegal CSR did not trap')
    finally:
        model.close()


def test_absent_pmp_does_not_allow_masks(tmp_path):
    config = json.loads((Path(__file__).parents[3] / 'examples/vexriscv/rvw/platform.json').read_text())
    config['csr_masks'] = {'0x3a0': '0xffffffff'}
    path = tmp_path / 'platform.json'
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match='compare exactly'):
        Platform.load('test', path)


def test_ecall_policy_updates_later_mtval_read(tmp_path_factory, tmp_path, platform):
    # Build a handler that observes the reference trap CSR after the event.
    source = tmp_path_factory.mktemp('ecall-source') / 'ecall.S'
    source.write_text(""".section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  ecall
handler:
  csrr a0, mtval
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
""")
    elf = _build(tmp_path_factory, source)
    p = copy.deepcopy(platform)
    p.ecall_tval = 'insn'
    rows = plain_trace(elf, p)
    read = next(r for r in rows if r.get('rd') == 10)
    assert read['rd_wdata'] == '0x73'
    assert run_check(tmp_path, rows, elf, p)['status'] == 'match'
    read['rd_wdata'] = '0x0'
    assert run_check(tmp_path, rows, elf, p)['status'] == 'mismatch'


@pytest.mark.parametrize('policy', ['trap', 'emulate'])
def test_policy_json_roundtrip(tmp_path, policy):
    config = json.loads((Path(__file__).parents[2] / 'src/rvw/cosim/configs/boom.json').read_text())
    config['misaligned'].update(load=policy, store=policy, atomic='trap' if policy == 'trap' else 'access_fault')
    config['privilege_modes'] = 'MU'
    path = tmp_path / 'platform.json'
    path.write_text(json.dumps(config))
    p = Platform.load('test', path)
    assert p.describe()['misaligned'] == config['misaligned']
    assert p.privilege_modes == 'MU'
    for key, value in [('store', 'trap' if policy == 'emulate' else 'emulate'),
                       ('atomic', 'emulate'), ('split_bus', 'allow'), ('split_page', 'allow')]:
        bad = copy.deepcopy(config)
        bad['misaligned'][key] = value
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError, match='unsupported misaligned policy'):
            Platform.load('test', path)


@pytest.mark.parametrize('opcode', ['lw a0, 1(t0)', 'sw zero, 1(t0)'])
def test_misaligned_failing_address_compares_strictly(tmp_path_factory, tmp_path, platform, opcode):
    elf = program(tmp_path_factory, 'la t0, buffer\n' + opcode)
    rows = plain_trace(elf, platform)
    assert run_check(tmp_path, rows, elf, platform)['status'] == 'match'
    event = next(r for r in rows if r.get('event') == 'trap')
    event['tval'] = hex(int(event['tval'], 16) + 1)
    result = run_check(tmp_path, rows, elf, platform)
    assert result['status'] == 'mismatch'
    assert 'tval' in result['mismatch']['differences']
