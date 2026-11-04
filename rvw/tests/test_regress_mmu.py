import json
import shutil
from pathlib import Path

import pytest

from rvw.regress.mmu import assembly, build, load, reference, validate

DESCRIPTION = Path(__file__).resolve().parents[2] / 'examples/boom/mmu/scenarios.json'


def scenario(**changes):
    return dict(id='load', level=0, flags='VRWAD', access='load', expect='success', bins=['load'], **changes)


@pytest.mark.parametrize('changes', [dict(level=3), dict(va='0x8000000000'), dict(pa=-1),
    dict(flags='BAD'), dict(asid=65536), dict(sum=1), dict(ad_expect=1), dict(fence='invalid'),
    dict(bins=[]), dict(extra=1)])
def test_invalid_description(changes):
    s = scenario()
    s.update(changes)
    with pytest.raises(ValueError):
        validate(s)


def test_duplicate_id(tmp_path):
    path = tmp_path / 'cases.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=[scenario(), scenario()])))
    with pytest.raises(ValueError, match='duplicate'):
        load(path)


def test_assembly_checks_fault_address_and_instruction():
    s = scenario()
    s['expect'] = 'page-fault'
    text = assembly(s)
    assert 'csrr t0, mcause' in text and 'li t1, 13' in text
    assert 'csrr t0, mtval' in text and 'csrr t0, mepc' in text
    assert 'access_site:\n ld a0, 0(t3)' in text
    assert 'csrc mstatus, t0\n j fail' in text


def test_table_depth():
    s = scenario()
    assert assembly(s).count('.dword') == 1540
    s['level'] = 2
    assert assembly(s).count('.dword') == 516


@pytest.mark.parametrize('returncode,timed_out,status', [(0,False,'pass'), (1,False,'fail'), (124,True,'inconclusive')])
def test_reference_bins_require_completion(tmp_path, monkeypatch, returncode, timed_out, status):
    from types import SimpleNamespace
    from rvw.regress import mmu
    elf = tmp_path / 'load.elf'
    elf.write_bytes(b'ELF')
    row = dict(scenario(), elf=elf.name, elf_sha256=mmu.digest(elf))
    (tmp_path / 'manifest.json').write_text(json.dumps({'scenarios':[row]}))
    monkeypatch.setattr(mmu.shutil, 'which', lambda _: str(elf))
    monkeypatch.setattr(mmu, 'run_group', lambda *a, **kw: SimpleNamespace(returncode=returncode, timed_out=timed_out, stderr='*** FAILED *** (tohost = 1)', stdout=''))
    result = reference(tmp_path, 'spike', 1)
    assert result['status'] == status
    assert result['scenarios'][0]['bins'] == {'load': status}
    elf.write_bytes(b'changed')
    with pytest.raises(ValueError, match='differs'):
        reference(tmp_path, 'spike', 1)


def test_native_spike(tmp_path):
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native RISC-V GCC and Spike required')
    build(DESCRIPTION, tmp_path, gcc)
    result = reference(tmp_path, spike, 5)
    assert result['status'] == 'pass', result


def test_scoped_remap_requires_global_invalidation():
    s = scenario(remap=True, fence='asid')
    text = assembly(s)
    assert text.count('sfence.vma x0, t4') == 2
    assert 'li t1, 43' in text and 'sd t1, 0(t0)' in text
    s['flags'] += 'G'
    with pytest.raises(ValueError, match='global'):
        assembly(s)


def test_ad_mask_is_checked_in_physical_memory():
    text = assembly(scenario(ad_expect=192))
    assert 'andi t0, t0, 192\n li t1, 192' in text


def test_native_hardware_ad(tmp_path):
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native RISC-V GCC and Spike required')
    build(DESCRIPTION.with_name('hardware-ad.json'), tmp_path, gcc)
    result = reference(tmp_path, spike, 5)
    assert result['status'] == 'pass', result


def test_pma_boundaries_and_conflicts(tmp_path):
    from rvw.regress.mmu import read_pma
    path = tmp_path / 'pma.json'
    region = dict(name='ram', start=0, size=4096, widths=[1,2,4,8], read=True,
                  write=True, execute=True, idempotent=True, cacheable=True, atomic=True)
    raw = dict(schema='rvw.mmu-pma/1', regions=[region, dict(region, start=4096)])
    path.write_text(json.dumps(raw))
    assert len(read_pma(path)['regions']) == 2
    raw['regions'][1]['start'] = 4095
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='overlapping'):
        read_pma(path)
    raw['regions'] = [dict(region, widths=[3])]
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match='widths'):
        read_pma(path)


@pytest.mark.parametrize('comparison,status', [
    ({'status':'match','trace_complete':True,'end_status':'pass','instructions':50,'synchronized':0},'pass'),
    ({'status':'match','trace_complete':False,'end_status':None,'instructions':50,'synchronized':0},'inconclusive'),
    ({'status':'match','trace_complete':True,'end_status':'pass','instructions':50,'synchronized':1},'inconclusive'),
    ({'status':'mismatch'},'fail'), ({'status':'error'},'inconclusive')])
def test_check_requires_complete_strict_match(tmp_path, monkeypatch, comparison, status):
    from types import SimpleNamespace
    from rvw.regress import mmu
    elf = tmp_path / 'load.elf'
    elf.write_bytes(b'ELF')
    (tmp_path / 'manifest.json').write_text(json.dumps({'scenarios': [dict(scenario(), elf=elf.name, elf_sha256=mmu.digest(elf))]}))
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'rvfi.jsonl').write_text('fixture')
    result = dict(schema='rvw.run/1', status='pass', elf_sha256=mmu.digest(elf), artifacts={'rvfi_trace':'rvfi.jsonl'})
    (run / 'result.json').write_text(json.dumps(result))
    def execute(command, **kwargs):
        assert '--strict' in command and '--model' in command
        assert '--core' in command and command[command.index('--core') + 1] == 'reference'
        return SimpleNamespace(stdout=json.dumps(comparison), returncode=0, timed_out=False)
    monkeypatch.setattr(mmu, 'run_group', execute)
    assert mmu.check(tmp_path, tmp_path, tmp_path/'platform.json', 'sail', 1)['status'] == status
    result['inconclusive'] = 'missing identity'
    (run / 'result.json').write_text(json.dumps(result))
    assert mmu.check(tmp_path, tmp_path, tmp_path/'platform.json', 'sail', 1)['status'] == 'inconclusive'


def test_store_changes_the_initial_value():
    s = scenario()
    s['access'] = 'store'
    text = assembly(s)
    assert 'li a0, 43\naccess_site:\n sd a0, 0(t3)' in text
    assert 'li t1, 43\n bne a0, t1, fail' in text
    assert '.section .data\n .dword 42' in text


def test_native_checker_detects_a_suppressed_store(tmp_path, monkeypatch):
    from rvw.regress import mmu
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native RISC-V GCC and Spike required')
    description = tmp_path / 'store.json'
    s = scenario()
    s['access'] = 'store'
    description.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=[s])))
    original = mmu.assembly
    monkeypatch.setattr(mmu, 'assembly', lambda row: original(row).replace('sd a0, 0(t3)', 'nop'))
    build(description, tmp_path/'build', gcc)
    result = reference(tmp_path/'build', spike, 5)
    assert result['status'] == 'fail'
    assert result['scenarios'][0]['bins'] == {'load': 'fail'}


def test_reference_tool_error_is_inconclusive(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from rvw.regress import mmu
    elf = tmp_path/'load.elf'
    elf.write_bytes(b'ELF')
    (tmp_path/'manifest.json').write_text(json.dumps({'scenarios':[dict(scenario(), elf=elf.name, elf_sha256=mmu.digest(elf))]}))
    monkeypatch.setattr(mmu.shutil, 'which', lambda _: str(elf))
    monkeypatch.setattr(mmu, 'run_group', lambda *a, **kw: SimpleNamespace(returncode=255, timed_out=False, stderr='unsupported extension', stdout=''))
    assert reference(tmp_path, 'spike', 1)['status'] == 'inconclusive'


def test_native_checker_detects_a_suppressed_load(tmp_path, monkeypatch):
    from rvw.regress import mmu
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native RISC-V GCC and Spike required')
    description = tmp_path / 'load.json'
    description.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=[scenario()])))
    original = mmu.assembly
    monkeypatch.setattr(mmu, 'assembly', lambda row: original(row).replace('ld a0, 0(t3)', 'nop'))
    build(description, tmp_path/'build', gcc)
    assert reference(tmp_path/'build', spike, 5)['status'] == 'fail'


@pytest.mark.parametrize('control,instruction', [('tvm','satp-read'), ('tvm','satp-write'),
    ('tvm','sfence'), ('tw','wfi'), ('tsr','sret')])
def test_control_fault_campaign(control, instruction):
    text = assembly(dict(id='control', control=control, instruction=instruction,
                         enabled=True, privilege='S', bins=['control']))
    assert 'mret' in text and 'csrr t0, mepc' in text
    assert 'li t1, 2' in text and 'la t1, access_site' in text


def test_wfi_clear_requires_a_wakeup_schedule():
    with pytest.raises(ValueError, match='interrupt schedule'):
        validate(dict(id='control', control='tw', instruction='wfi', enabled=False,
                      privilege='S', bins=['control']))


@pytest.mark.parametrize('changes', [dict(offset=-1), dict(offset=4096), dict(value=-1),
    dict(unfenced=True), dict(switch_asid=True), dict(walk_deny=1)])
def test_corner_case_validation(changes):
    s = scenario(); s.update(changes)
    with pytest.raises(ValueError):
        validate(s)


def test_native_checker_rejects_suppressed_sret(tmp_path, monkeypatch):
    from rvw.regress import mmu
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native RISC-V GCC and Spike required')
    s = dict(id='sret', control='tsr', instruction='sret', enabled=False, privilege='S', bins=['sret'])
    path = tmp_path/'case.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=[s])))
    original = mmu.assembly
    monkeypatch.setattr(mmu, 'assembly', lambda row: original(row).replace('\n sret\n', '\n nop\n'))
    build(path, tmp_path/'build', gcc)
    assert reference(tmp_path/'build', spike, 5)['status'] == 'fail'


def test_report_needs_bound_check_and_unique_c1(tmp_path):
    from rvw.regress import mmu
    elf = tmp_path/'load.elf'; elf.write_bytes(b'elf')
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'scenarios': [dict(scenario(), elf=elf.name, elf_sha256=mmu.digest(elf))]}))
    run = tmp_path/'run'; run.mkdir()
    c1 = run/'result.json'
    c1.write_text(json.dumps(dict(schema='rvw.run/1', status='pass', elf_sha256=mmu.digest(elf))))
    result = mmu.report(tmp_path, run)
    assert result['counts'] == {'pass': 0, 'fail': 0, 'inconclusive': 1}
    checked = tmp_path/'checked.json'
    checked.write_text(json.dumps(dict(schema='rvw.mmu-check/1', manifest_sha256=mmu.digest(manifest),
        scenarios=[dict(id='load', elf_sha256=mmu.digest(elf), c1_sha256=mmu.digest(c1), status='pass')])))
    assert mmu.report(tmp_path, run, checked)['counts']['pass'] == 1
    assert mmu.report(tmp_path, run, checked)['scenarios'][0]['observations']['status'] == 'inconclusive'
    c1.write_text(c1.read_text()+'\n')
    assert mmu.report(tmp_path, run, checked)['counts']['pass'] == 0
    manifest.write_text(manifest.read_text()+'\n')
    with pytest.raises(ValueError, match='coverage needs'):
        mmu.report(tmp_path, run, checked)


def test_report_keeps_observations_separate_from_architectural_bins(tmp_path):
    from rvw.regress import mmu
    elf = tmp_path/'load.elf'; elf.write_bytes(b'elf')
    (tmp_path/'manifest.json').write_text(json.dumps({'scenarios': [dict(scenario(), elf=elf.name, elf_sha256=mmu.digest(elf))]}))
    run = tmp_path/'run'; run.mkdir()
    observations = run/'observed.jsonl'
    observations.write_text('\n'.join(map(json.dumps, [
        dict(schema='rvw.mmu-observations/1', elf_sha256=mmu.digest(elf)),
        dict(kind='walk_request', cycle=1, address='0x80010008', command=0),
        dict(kind='bus_a', cycle=2, address='0x2000000', opcode=4, size_log2=3)])))
    (run/'result.json').write_text(json.dumps(dict(schema='rvw.run/1', status='pass',
        elf_sha256=mmu.digest(elf), details=dict(mmu_observations=observations.name))))
    result = mmu.report(tmp_path, run)
    assert result['counts'] == {'pass': 0, 'fail': 0, 'inconclusive': 1}
    observed = result['scenarios'][0]['observations']
    assert observed['status'] == 'recorded'
    assert observed['counts'] == dict(walk_request=1, walk_response=0, bus_a=1)
    assert observed['sha256'] == mmu.digest(observations)
    observations.write_text(json.dumps(dict(schema='rvw.mmu-observations/1', elf_sha256='wrong')))
    with pytest.raises(ValueError, match='header'):
        mmu.report(tmp_path, run)


def test_unfenced_oracle_divergence_cannot_earn_a_pass(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from rvw.regress import mmu
    elf = tmp_path/'load.elf'; elf.write_bytes(b'ELF')
    s = scenario(remap=True, unfenced=True)
    (tmp_path/'manifest.json').write_text(json.dumps({'scenarios': [dict(s, elf=elf.name, elf_sha256=mmu.digest(elf))]}))
    run = tmp_path/'run'; run.mkdir(); (run/'rvfi.jsonl').write_text('fixture')
    (run/'result.json').write_text(json.dumps(dict(schema='rvw.run/1', status='pass',
        elf_sha256=mmu.digest(elf), artifacts={'rvfi_trace': 'rvfi.jsonl'})))
    monkeypatch.setattr(mmu, 'run_group', lambda *a, **k: SimpleNamespace(
        stdout=json.dumps({'status': 'mismatch'}), returncode=1, timed_out=False))
    result = mmu.check(tmp_path, run, tmp_path/'platform.json', 'sail', 1)
    assert result['status'] == 'inconclusive'
    assert result['scenarios'][0]['comparison']['status'] == 'mismatch'
    assert result['scenarios'][0]['c1_status'] == 'pass'


def test_clint_msip_uses_declared_register_width():
    row = next(s for s in load(DESCRIPTION) if s['id'] == 'clint-msip-read')
    soc = json.loads((DESCRIPTION.parents[1] / 'soc.json').read_text())
    clint = next(r for r in soc['regions'] if r['name'] == 'clint')
    msip = next(r for r in clint['registers'] if r['name'] == 'msip')
    assert row['register_width'] == msip['width'] == 32
    assert 'access_site:\n lw a0, 0(t3)' in assembly(row)


@pytest.mark.parametrize('access', ['load', 'store'])
def test_generation_refuses_access_wider_than_register(access):
    row = scenario(access_width=8, register_width=32)
    row['access'] = access
    with pytest.raises(ValueError, match='register width'):
        assembly(row)


@pytest.mark.parametrize('width,load_op,store_op', [(1, 'lb', 'sb'), (2, 'lh', 'sh'), (4, 'lw', 'sw'), (8, 'ld', 'sd')])
def test_access_width_selects_load_store_and_readback(width, load_op, store_op):
    row = scenario(access_width=width, register_width=width * 8)
    assert f'access_site:\n {load_op} a0, 0(t3)' in assembly(row)
    row['access'] = 'store'
    text = assembly(row)
    assert f'access_site:\n {store_op} a0, 0(t3)' in text
    assert f'{load_op} a0, 0(t0)' in text


@pytest.mark.parametrize('changes', [dict(access_width=True), dict(access_width=3),
    dict(register_width=True), dict(register_width=4), dict(register_width=32),
    dict(access_width=4, remap=True)])
def test_invalid_access_width(changes):
    with pytest.raises(ValueError):
        assembly(scenario(**changes))


def test_native_reserved_satp_mode_write_is_ignored(tmp_path, monkeypatch):
    from rvw.regress import mmu
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native RISC-V GCC and Spike required')
    row = dict(id='satp-warl', control='satp-mode', instruction='reserved-mode-write',
               enabled=False, privilege='M', bins=['satp-warl'])
    path = tmp_path/'case.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=[row])))
    build(path, tmp_path/'good', gcc)
    assert reference(tmp_path/'good', spike, 5)['status'] == 'pass'
    original = mmu.assembly
    def supported_mode(s):
        # A supported mode must not have the ignored-write behavior.
        return original(s).replace(str((1 << 60) | (7 << 44) | ((mmu.ROOT + 4096) >> 12)),
                                   str((8 << 60) | (7 << 44) | ((mmu.ROOT + 4096) >> 12)))
    monkeypatch.setattr(mmu, 'assembly', supported_mode)
    build(path, tmp_path/'bad', gcc)
    assert reference(tmp_path/'bad', spike, 5)['status'] == 'fail'


def test_tw_clear_pending_ssip_wakes_with_global_interrupts_disabled():
    row = dict(id='wakeup', control='tw', instruction='wfi', enabled=False,
               privilege='S', wakeup='pending-ssip', bins=['wakeup'])
    text = assembly(row)
    assert 'csrw mideleg, t0\n csrw mie, t0\n csrs mip, t0' in text
    assert 'li t0, 0x7e190a' in text  # Clear both global enables before mret.
    assert 'li t1, 9' in text and 'la t1, done' in text
    row['privilege'] = 'U'
    with pytest.raises(ValueError, match='wakeup'):
        assembly(row)


def test_fetch_uses_real_privilege_and_exact_fault_pc():
    row = dict(id='fetch', level=0, flags='VRAD', access='fetch',
               expect='page-fault', bins=['fetch'])
    text = assembly(row)
    assert 'csrw mepc, t3\n mret' in text
    assert 'li t1, 12' in text and 'csrr t0, mtval' in text
    assert '.word 0x00000073' in text
    row['remap'] = True
    with pytest.raises(ValueError, match='fetch'):
        assembly(row)


def test_native_fetch_checker_rejects_wrong_execute_permission(tmp_path, monkeypatch):
    from rvw.regress import mmu
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native RISC-V GCC and Spike required')
    row = dict(id='fetch', level=0, flags='VRXAD', access='fetch',
               expect='success', bins=['fetch'], ad_mode='svade')
    path = tmp_path/'case.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=[row])))
    original = mmu.assembly
    def wrong_permission(s):
        # Change only the generated leaf, while retaining the success oracle.
        old = ((mmu.DATA >> 12) << 10) | 0xcb
        return original(s).replace(f'.dword {old}', f'.dword {old & ~8}')
    monkeypatch.setattr(mmu, 'assembly', wrong_permission)
    build(path, tmp_path/'build', gcc)
    assert reference(tmp_path/'build', spike, 5)['status'] == 'fail'


def test_walk_checker_uses_pte_values_and_physical_target():
    from rvw.regress.mmu_observe import check_walk
    events = []
    for i, (address, value) in enumerate([(0x80010008, 0x20004401),
             (0x80011000, 0x20004801), (0x80012000, 0x200800c7)]):
        events += [dict(kind='walk_request', cycle=2*i, address=hex(address), command=0),
                   dict(kind='walk_response', cycle=2*i+1, address=hex(address), data=hex(value))]
    assert check_walk(scenario(), events)['status'] == 'inconclusive'
    events.append(dict(kind='bus_a', cycle=7, address='0x80200000', opcode=6, size_log2=6))
    assert check_walk(scenario(), events)['status'] == 'consistent'
    events[3]['data'] = '0xdeadbeef'
    assert check_walk(scenario(), events)['status'] == 'mismatch'
    events[3]['data'] = '0x20004801'
    events[0]['address'] = '0x80010010'
    assert check_walk(scenario(), events)['status'] == 'mismatch'
    assert check_walk(scenario(remap=True), events)['status'] == 'inconclusive'


def test_walk_checker_superpage_target_uses_low_virtual_bits():
    from rvw.regress.mmu_observe import check_walk
    row = scenario(); row.update(level=2, pa='0x80000000', va='0x40200000')
    result = check_walk(row, [])
    assert result['physical_target'] == '0x80200000'
    with pytest.raises(ValueError, match='ordered'):
        check_walk(scenario(), [dict(kind='bus_a', cycle=c, address='0x0', opcode=4,
                                    size_log2=3) for c in (5, 4)])
