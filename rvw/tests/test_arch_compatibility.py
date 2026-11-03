"""Static layout checks. No core behavior or RV32 runtime is validated here."""
import struct

import pytest

from rvw.arch import core
from test_arch_model import make_elf, model


def elf32(tmp_path):
    data = bytearray(1024)
    data[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHIIIIIHHHHHH', data, 16, 2, 243, 1, 0x80000000, 52, 128,
                     0, 52, 32, 1, 40, 3, 0)
    struct.pack_into('<IIIIIIII', data, 52, 1, 0, 0x80000000, 0x80000000, 1024, 1024, 7, 4096)
    # Null, string table and symbol table sections.
    names = b'\0tohost\0tohost_exit\0setStats\0bench_stats\0'
    data[300:300+len(names)] = names
    struct.pack_into('<IIIIIIIIII', data, 168, 0, 3, 0, 0, 300, len(names), 0, 0, 1, 0)
    struct.pack_into('<IIIIIIIIII', data, 208, 0, 2, 0, 0, 400, 80, 1, 1, 4, 16)
    for i, (name, addr, size) in enumerate([
        ('tohost', 0x80000300, 8), ('tohost_exit', 0x80000000, 4),
        ('setStats', 0x80000004, 4), ('bench_stats', 0x80000310, 16)], 1):
        struct.pack_into('<IIIBBH', data, 400+i*16, names.index(name.encode()), addr, size, 0, 0, 1)
    path = tmp_path / 'rv32.riscv'
    path.write_bytes(data)
    return path


def test_rv32_static_check_keeps_runtime_blocked(tmp_path, rvw):
    path = elf32(tmp_path)
    symbols = model.elf_symbols(path, xlen=32)
    assert symbols['bench_stats'] == (0x80000310, 16)
    result = core.inspect(path, 'rv32im', 'minor')
    assert result['status'] == 'unsupported' and len(result['blockers']) == 2
    code, _, report = rvw('arch', 'inspect', '--elf', path, '--isa', 'rv32im', '--kind', 'minor', '--json')
    assert code == 2 and report['status'] == 'unsupported'
    # The simulation entry still uses default xlen=64 and must refuse ELF32.
    with pytest.raises(ValueError, match='ELF64'):
        model.elf_symbols(path)


def test_rv64_static_compatibility_is_not_calibration(tmp_path, rvw):
    path, _, _ = make_elf(tmp_path)
    result = core.inspect(path, 'rv64gc', 'o3')
    assert result['status'] == 'compatible' and not result['blockers']
    assert 'Static ELF' in result['limits']
    assert core.inspect(path, 'rv64gc', 'timing')['status'] == 'unsupported'
    assert rvw('arch', 'inspect', '--elf', path, '--isa', 'rv64gc', '--kind', 'o3', '--json')[0] == 0


@pytest.mark.parametrize('damage', ['truncated', 'machine', 'undefined', 'short', 'outside'])
def test_bad_elf32_refuses(tmp_path, damage):
    path = elf32(tmp_path)
    data = bytearray(path.read_bytes())
    if damage == 'truncated': data = data[:40]
    if damage == 'machine': struct.pack_into('<H', data, 18, 62)
    if damage == 'undefined': struct.pack_into('<H', data, 416+14, 0)
    if damage == 'short': struct.pack_into('<I', data, 464+8, 8)
    if damage == 'outside': struct.pack_into('<I', data, 52+12, 0)
    path.write_bytes(data)
    with pytest.raises(ValueError): model.elf_symbols(path, xlen=32)


@pytest.mark.parametrize('isa,kind', [('rv32im', 'o3'), ('rv64gc', 'minor'), ('rv32im', 'timing')])
def test_known_unsupported_combinations_stay_blocked(tmp_path, isa, kind):
    path = elf32(tmp_path) if isa == 'rv32im' else make_elf(tmp_path)[0]
    assert core.inspect(path, isa, kind)['status'] == 'unsupported'


@pytest.mark.parametrize('isa,kind', [('rv128gc', 'o3'), ('rv64gc', 'invented')])
def test_unknown_selection_fails_before_read(tmp_path, isa, kind):
    with pytest.raises(ValueError, match='unsupported'):
        core.inspect(tmp_path / 'absent', isa, kind)
