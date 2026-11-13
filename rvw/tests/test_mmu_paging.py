"""Paging tests use no DUT or core checkout."""
import json
import shutil

import pytest

from rvw.regress import mmu
from rvw.regress.mmu_paging import MODES, matrix, page_tables


@pytest.mark.parametrize('mode', MODES)
def test_geometry_and_tables(mode):
    g = MODES[mode]
    for level in range(g.levels):
        s = dict(mode=mode, level=level, va=0x40000000)
        pages, leaf = page_tables(s, mmu.ROOT, mmu.DATA, 0xc7)
        assert len(pages) == g.levels - level
        assert all(len(p) * g.width == 4096 for p in pages)
        assert pages[-1][(leaf % 4096) // g.width] == (mmu.DATA >> 12 << 10) | 0xc7
        assert g.satp(mmu.ROOT, 7) & ((1 << (22 if g.xlen == 32 else 44)) - 1) == mmu.ROOT >> 12


@pytest.mark.parametrize('mode', MODES)
def test_matrix_validation(mode):
    cases = matrix({'modes': [mode]})
    assert len({s['id'] for s in cases}) == len(cases)
    for s in cases:
        mmu.validate(s)
        assert ('csrw mepc, t3' if s['access'] == 'fetch' else 'access_site:') in mmu.assembly(s)


def test_noncanonical_requires_fault():
    s = matrix({'modes': ['sv48']})[0]
    s.update(va=1 << 47, expect='success')
    with pytest.raises(ValueError, match='canonical'):
        mmu.validate(s)


def test_project_matrix_load(tmp_path):
    path = tmp_path / 'matrix.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', matrix={'modes': ['sv57']})))
    assert all(s['mode'] == 'sv57' for s in mmu.load(path))


@pytest.mark.parametrize('mode', MODES)
def test_spike_matrix(tmp_path, mode):
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    desc = tmp_path / 'cases.json'
    desc.write_text(json.dumps(dict(schema='rvw.mmu/1', matrix={'modes': [mode]})))
    mmu.build(desc, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    bad = [(s['id'], s['status'], s['stderr']) for s in result['scenarios'] if s['status'] != 'pass']
    assert not bad, bad


@pytest.mark.parametrize('mode', MODES)
def test_walk_geometry(mode):
    from rvw.regress.mmu_observe import check_walk
    g = MODES[mode]
    s = dict(mode=mode, level=0, flags='VRWAD', access='load', expect='success')
    events = []
    for depth in range(g.levels):
        level = g.levels - depth - 1
        addr = mmu.ROOT + depth * 4096 + ((0x40000000 >> (12 + g.vpn_bits * level)) & ((1 << g.vpn_bits) - 1)) * g.width
        pte = ((mmu.ROOT + (depth + 1) * 4096) >> 12 << 10) | 1 if level else (mmu.DATA >> 12 << 10) | 0xc7
        events.extend([dict(kind='walk_request', cycle=depth * 2, address=addr, command=0), dict(kind='walk_response', cycle=depth * 2 + 1, address=addr, data=pte)])
    events.append(dict(kind='bus_a', cycle=20, address=mmu.DATA, opcode=4, size_log2=3))
    assert check_walk(s, events)['status'] == 'consistent'
    events[1]['data'] ^= 0x1000
    assert check_walk(s, events)['status'] == 'mismatch'


def test_spike_extensions(tmp_path):
    from pathlib import Path
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    desc = Path(__file__).resolve().parents[2] / 'examples/mmu/extensions.json'
    mmu.build(desc, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    assert result['status'] == 'pass', [(s['id'], s['status'], s['stderr']) for s in result['scenarios'] if s['status'] != 'pass']


def test_permission_controls_are_independent():
    rows = matrix({'modes': ['sv39']})
    assert {(s['sum'], s['mxr']) for s in rows if 'sum' in s} == {(False, False), (False, True), (True, False), (True, True)}


@pytest.mark.parametrize('change', [dict(mode='sv32', pbmt=1), dict(mode='sv39', pbmt=4), dict(mode='sv39', napot=True, level=1), dict(mode='sv39', napot_ppn=0), dict(mode='sv32', asid=512)])
def test_invalid_extension_and_mode_config(change):
    s = dict(id='bad', level=0, flags='VRWAD', access='load', expect='success', bins=['bad'])
    s.update(change)
    with pytest.raises(ValueError):
        mmu.validate(s)


def test_spike_guest(tmp_path):
    from pathlib import Path
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    desc = Path(__file__).resolve().parents[2] / 'examples/mmu/guest.json'
    mmu.build(desc, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    assert result['status'] == 'pass', result


def test_spike_shootdown(tmp_path):
    from pathlib import Path
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    desc = Path(__file__).resolve().parents[2] / 'examples/mmu/shootdown.json'
    mmu.build(desc, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    assert result['status'] == 'pass', result
