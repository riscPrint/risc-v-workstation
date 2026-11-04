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
