import copy
import json
import pytest
from rvw.cosim.qemu import compare
from test_state import fixture


def inputs(tmp_path):
    header, row = fixture()
    header['schema'] = 'rvw.rvfi/1'
    row = {k: v for k, v in row.items() if k not in ('fd_valid', 'fd', 'fd_wdata', 'fflags', 'fcsr')}
    row.update(insn='0x700513', rd=10, rd_wdata='0x7')
    trace = tmp_path/'trace.jsonl'
    records = [header, row, dict(event='end', cycle=2, status='pass')]
    trace.write_text('\n'.join(map(json.dumps, records)))
    return trace, records


def test_match_mutation_and_missing_state(tmp_path):
    trace, rows = inputs(tmp_path)
    log = tmp_path/'qemu.log'
    def snapshot(pc, a0):
        return ' pc '+hex(pc)[2:]+'\n'+''.join(f' x{i}/r{i} {a0 if i == 10 else 0:016x}\n' for i in range(32))
    log.write_text(snapshot(0x1000, 0)+snapshot(0x80000000, 0)+snapshot(0x80000004, 7))
    result = compare(trace, log)
    assert result['status'] == 'match'
    assert not result['architectural_match']
    assert result['skipped_prefix'] == 1
    rows[1]['rd_wdata'] = '0x8'
    trace.write_text('\n'.join(map(json.dumps, rows)))
    assert compare(trace, log)['status'] == 'mismatch'
    log.write_text(' pc 80000000\n x0/zero 0\n')
    with pytest.raises(ValueError, match='complete integer'):
        compare(trace, log)


def test_native_qemu_cpu_log(tmp_path, tmp_path_factory):
    import shutil
    from cosim_build import _build
    from rvw.common.proc import run_group
    qemu = shutil.which('qemu-system-riscv64')
    if not qemu:
        pytest.skip('QEMU RISC-V system emulator not installed')
    source = tmp_path/'qemu.S'
    source.write_text('.section .text\n.globl _start\n_start: li a0,7\n nop\n wfi\n')
    elf = _build(tmp_path_factory, source)
    log = tmp_path/'qemu.log'
    run_group(['nice', '-n', '10', qemu, '-machine', 'virt', '-smp', '1', '-m', '128M',
               '-bios', 'none', '-kernel', str(elf), '-display', 'none', '-serial', 'none',
               '-monitor', 'none', '-accel', 'tcg,one-insn-per-tb=on', '-d', 'cpu,nochain',
               '-D', str(log)], capture=True, timeout=1)
    trace, _ = inputs(tmp_path)
    result = compare(trace, log)
    assert result['status'] == 'match', result
    assert result['instructions'] == 1


def test_async_event_is_inconclusive(tmp_path):
    trace, rows = inputs(tmp_path)
    rows.insert(1, dict(event='irq', cycle=0, levels='0x80'))
    trace.write_text('\n'.join(map(json.dumps, rows)))
    log = tmp_path/'qemu.log'
    log.write_text('')
    result = compare(trace, log)
    assert result['status'] == 'inconclusive'
    assert result['cause'] == 'event_synchronization_unsupported'


def test_optional_third_reference_preserves_scope(monkeypatch):
    from rvw.cosim.adjudicate import execute_json
    base = dict(status='match', instructions=1, trace_complete=True,
                reproduction=dict(elf_sha256='e', trace_sha256='t', platform_sha256='p'))
    monkeypatch.setattr('rvw.cosim.cli.execute_json', lambda *a, **kw: copy.deepcopy(base))
    monkeypatch.setattr('rvw.cosim.qemu.execute_json', lambda **kw: dict(status='mismatch', trace_sha256='t', architectural_match=False))
    report = execute_json(elf='elf', trace='trace', qemu_log='log')
    assert report['status'] == 'disagreement'
    assert set(report['matched_references']) == {'spike', 'sail'}
    assert report['qemu_role'] == 'partial_boot_observations'
    assert not report['references']['qemu']['architectural_match']
