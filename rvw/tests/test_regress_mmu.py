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
    assert assembly(s).count('.dword') == 1539
    s['level'] = 2
    assert assembly(s).count('.dword') == 515


@pytest.mark.parametrize('returncode,timed_out,status', [(0,False,'pass'), (1,False,'fail'), (124,True,'inconclusive')])
def test_reference_bins_require_completion(tmp_path, monkeypatch, returncode, timed_out, status):
    from types import SimpleNamespace
    from rvw.regress import mmu
    elf = tmp_path / 'load.elf'
    elf.write_bytes(b'ELF')
    row = dict(scenario(), elf=elf.name, elf_sha256=mmu.digest(elf))
    (tmp_path / 'manifest.json').write_text(json.dumps({'scenarios':[row]}))
    monkeypatch.setattr(mmu, 'run_group', lambda *a, **kw: SimpleNamespace(returncode=returncode, timed_out=timed_out, stderr=''))
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
