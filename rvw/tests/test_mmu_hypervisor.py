import json
import shutil
import pytest
from rvw.regress import mmu


from rvw.regress.mmu_hypervisor import matrix


def test_geometries_and_operations():
    for s in matrix():
        mmu.validate(s)
        asm = mmu.assembly(s)
        assert ('mret' if s.get('guest_op', 'hlv.d').startswith('vs-') else s.get('guest_op', 'hlv.d') + ' a0, (t3)') in asm
        assert 'csrw hgatp, t0' in asm


def test_spike_matrix(tmp_path):
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    path = tmp_path / 'guest.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=matrix())))
    mmu.build(path, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    assert result['status'] == 'pass', [(r['id'], r['stderr']) for r in result['scenarios'] if r['status'] != 'pass']


@pytest.mark.parametrize('mode', ['sv39', 'sv48', 'sv57'])
def test_independent_nested_walk(mode):
    from rvw.regress.mmu_paging import MODES, page_tables
    from rvw.regress.mmu_nested import translate
    g = MODES[mode]
    pages, _ = page_tables(dict(mode=mode, level=0), mmu.ROOT, mmu.DATA, 0xcf)
    memory = {mmu.ROOT + d * 4096 + i * 8: p for d, table in enumerate(pages) for i, p in enumerate(table)}
    root = 0x80020000
    # Identity G superpage at the largest level that fits 0x80000000.
    table = root
    for level in reversed(range(g.levels)):
        index = 0x80000000 >> (12 + level * 9) & (2047 if level == g.levels - 1 else 511)
        if level == 2:
            memory[table + index * 8] = (0x80000000 >> 12 << 10) | 0xdf
            break
        memory[table + index * 8] = ((table + 16384) >> 12 << 10) | 1
        table += 16384
    arguments = dict(vs_mode=mode, vs_root=mmu.ROOT, g_mode=mode, g_root=root, va=0x40000000, access='load', memory=memory)
    result = translate(**arguments)
    assert result['status'] == 'success' and result['pa'] == mmu.DATA
    assert len(result['g_walks']) == g.levels + 1
    memory[table + index * 8] = 0
    result = translate(**arguments)
    assert result['status'] == 'guest-page-fault'
    assert result['htval'] == (mmu.ROOT + ((0x40000000 >> (12 + 9 * (g.levels - 1))) & 511) * 8) >> 2


@pytest.mark.parametrize('mode', ['sv39', 'sv48', 'sv57'])
def test_x4_widened_root(mode):
    from rvw.regress.mmu_walk import walk
    from rvw.regress.mmu_paging import MODES
    g = MODES[mode]
    va = (1 << (g.va_bits + 2)) - 4096
    table, memory = 0x80020000, {}
    for level in reversed(range(g.levels)):
        index = va >> (12 + 9 * level) & (2047 if level == g.levels - 1 else 511)
        memory[table + index * 8] = ((table + 16384) >> 12 << 10) | 1 if level else (mmu.DATA >> 12 << 10) | 0xdf
        table += 16384
    result = walk(mode=mode, root=0x80020000, va=va, access='load', memory=memory, privilege='U', x4=True)
    assert result['status'] == 'success' and result['pa'] == mmu.DATA
    assert walk(mode=mode, root=0x80020000, va=va, access='load', memory=memory)['status'] == 'page-fault'
