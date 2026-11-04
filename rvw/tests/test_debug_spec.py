"""Tool tests and bounded native reference checks. No core conformance claims."""
import configparser
from contextlib import contextmanager
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import sys
import threading
import time

import pytest

from rvw.common.proc import run_group
from rvw.debug import campaign, etrace
from rvw.debug.dmi import RemoteDMI

FIXTURES = Path(__file__).parent / 'fixtures/debug'
GCC = '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
TOOLCHAIN = Path(os.environ.get('RISCV_TOOLCHAIN', '/opt/homebrew/opt/riscv-gnu-toolchain'))


def build(tmp_path, name):
    gcc = shutil.which('riscv64-unknown-elf-gcc') or GCC
    if not Path(gcc).is_file():
        pytest.skip('native RISC-V GCC is unavailable')
    elf = tmp_path / (name + '.elf')
    result = run_group([gcc, '-nostdlib', '-march=rv64imac', '-mabi=lp64',
                        '-Wl,-Ttext=0x80000000,--no-relax,-z,max-page-size=4096',
                        '-o', str(elf), str(FIXTURES / (name + '.S'))], capture=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return elf


@contextmanager
def spike_target(tmp_path, *options):
    if not shutil.which('spike'):
        pytest.skip('native Spike is unavailable')
    elf = build(tmp_path, 'loop')
    with socket.socket() as port_socket:
        port_socket.bind(('127.0.0.1', 0))
        port = port_socket.getsockname()[1]
    pids, result = [], []
    with (tmp_path / 'spike.log').open('w+') as log:
        thread = threading.Thread(target=lambda: result.append(run_group(
            ['spike', f'--rbb-port={port}', '--halted', '-m0x7ffff000:0x1001000',
             *options, str(elf)], stdout=log, stderr=log, timeout=35, on_start=pids.append)))
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if 'Listening for remote bitbang' in (tmp_path / 'spike.log').read_text():
                    break
                if not thread.is_alive():
                    pytest.fail((tmp_path / 'spike.log').read_text())
                time.sleep(.02)
            else:
                pytest.fail('Spike did not open its JTAG listener')
            yield port
        finally:
            if pids:
                try:
                    os.killpg(pids[0], signal.SIGTERM)
                except ProcessLookupError:
                    pass
            thread.join(10)
            assert not thread.is_alive()


def test_campaign_no_false_pass():
    output = '\n'.join('RVW_CHECK:' + c for c in campaign.CHECKS)
    assert campaign.assess(0, output)['status'] == 'inconclusive'
    assert campaign.assess(0, 'RVW_FAILURE:assertion failed')['status'] == 'fail'
    output += '\nRVW_COMPLETE:debug-0.13.2-rv64'
    assert campaign.assess(0, output)['status'] == 'pass'
    assert campaign.assess(1, output)['status'] == 'fail'
    assert campaign.assess(0, output, True)['status'] == 'inconclusive'
    assert campaign.assess(0, output.replace('RVW_CHECK:halted', 'missing'))['status'] == 'fail'


@pytest.mark.parametrize('decoded,expected,complete,loss,status', [
    ([2, 4], [2, 4], True, False, 'flow_match'),
    ([2, 4], [2, 6], True, False, 'mismatch'),
    ([2], [2, 4], True, False, 'mismatch'),
    ([2, 4, 6], [2, 4], True, False, 'mismatch'),
    ([], [], True, False, 'inconclusive'),
    ([2], [2], False, False, 'inconclusive'),
    ([2], [2], True, True, 'inconclusive'),
])
def test_flow_verdict(decoded, expected, complete, loss, status):
    assert etrace.compare(decoded, expected, complete=complete, loss=loss)['status'] == status


def test_invalid_reference(tmp_path):
    with pytest.raises(ValueError, match='clean reference'):
        etrace.verify_reference(tmp_path)


def test_ingress_rejects_unsupported(tmp_path):
    row = dict(pc=0x1000, pc_next=0x1004, insn=0x13, mode=3)
    etrace.ingress([row], tmp_path / 'in')
    assert '0,0,0,3,1000,0,0,1,1' in (tmp_path / 'in').read_text()
    for change in ({'trap': True}, {'intr': True}, {'mode': 1}, {'insn': 0xffffffff}):
        with pytest.raises(ValueError):
            etrace.ingress([{**row, **change}], tmp_path / 'bad')


@pytest.mark.parametrize('bad', ['garbage', '2 4', '-2', '3', '10000000000000000'])
def test_bad_pc(tmp_path, bad):
    path = tmp_path / 'pcs'
    path.write_text(bad)
    with pytest.raises(ValueError):
        etrace.read_pcs(path)


def test_openocd_spike(tmp_path):
    if not shutil.which('openocd'):
        pytest.skip('native OpenOCD is unavailable')
    with spike_target(tmp_path) as port:
        config = tmp_path / 'target.cfg'
        config.write_text(f'''adapter driver remote_bitbang
remote_bitbang host 127.0.0.1
remote_bitbang port {port}
transport select jtag
jtag newtap dut cpu -irlen 5 -expected-id 0xdeadbeef
target create dut.cpu riscv -chain-position dut.cpu
gdb_port disabled
tcl_port disabled
telnet_port disabled
init
''')
        result = campaign.run(config, log=tmp_path / 'openocd.log')
        assert result['status'] == 'pass', (tmp_path / 'openocd.log').read_text()
        assert set(result['checks']) == campaign.CHECKS


@pytest.mark.parametrize('idle', [0, 4])
def test_dmi_spike(tmp_path, idle):
    with spike_target(tmp_path, f'--dmi-rti={idle}') as port:
        dmi = RemoteDMI('127.0.0.1', port)
        try:
            assert dmi.abits == 7
            dmi.access(0x10, 1, write=True)
            assert dmi.access(0x11) & 0xf == 2
            dmi.access(0x10, 0x80000001, write=True)
            for _ in range(100):
                if dmi.access(0x11) & 0x300 == 0x300:
                    break
            else:
                pytest.fail('hart did not halt')
            dmi.access(4, 0x12345678, write=True)
            assert dmi.access(4) == 0x12345678
            dmi.access(0x10, 0x40000001, write=True)
            for _ in range(100):
                if dmi.access(0x11) & 0xc00 == 0xc00:
                    break
            else:
                pytest.fail('hart did not resume')
            with pytest.raises(ValueError):
                dmi.access(1 << dmi.abits)
        finally:
            dmi.close()


def test_reference_etrace_spike(tmp_path):
    reference = os.environ.get('RVW_ETRACE_REFERENCE')
    if not reference or not shutil.which('spike') or not (TOOLCHAIN / 'bin/riscv64-unknown-elf-objdump').is_file():
        pytest.skip('set RVW_ETRACE_REFERENCE to the pinned native reference checkout')
    root = etrace.verify_reference(reference)
    elf = build(tmp_path, 'trace')
    log = tmp_path / 'execution.log'
    result = run_group(['spike', '--isa=rv64imac', '--instructions=120', '-l', f'--log={log}',
                        '-m0x7ffff000:0x1001000', str(elf)], capture=True, timeout=10)
    assert result.returncode == 0, result.stderr
    executed = [(int(pc, 16), int(insn, 16)) for pc, insn in re.findall(
        r'core\s+0:\s+0x([0-9a-f]+)\s+\(0x([0-9a-f]+)\)', log.read_text())
        if int(pc, 16) >= 0x80000000]
    assert len(executed) > 50
    rows = [dict(pc=pc, insn=insn, pc_next=executed[i+1][0], mode=3)
            for i, (pc, insn) in enumerate(executed[:-1])]
    ingress = tmp_path / 'native_input'
    etrace.ingress(rows, ingress)
    config = root / 'referenceFlow/tests/config_files'
    static = tmp_path / 'static.scf'
    static.write_text((config / 'i_template.scf').read_text())
    user = configparser.ConfigParser()
    user.read(config / 'i_template.ucf')
    user['required']['file-stem'] = str(tmp_path / 'native')
    user['required']['object-files'] = str(elf)
    ucf = tmp_path / 'user.ucf'
    with ucf.open('w') as stream:
        user.write(stream)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    encoder = run_group([sys.executable, str(root / 'referenceFlow/scripts/encoder_model.py'),
                         '-c', str(static), '-u', str(ucf)], env=env, cwd=tmp_path,
                        timeout=15, capture=True)
    assert encoder.returncode == 0, (encoder.stdout, encoder.stderr)
    expected = [r['pc'] for r in rows]
    for suffix in ('te_inst', 'te_inst_raw'):
        packets = tmp_path / ('native_input.' + suffix)
        decoded, identity = etrace.decode(root, packets, static, ucf, toolchain=TOOLCHAIN)
        assert identity['decoder_rev'] == etrace.REFERENCE_REV
        assert etrace.compare(decoded, expected, complete=True)['status'] == 'flow_match'
        # Simulated packet truncation must never pass an exact comparison.
        assert etrace.compare(decoded[:-1], expected, complete=True)['status'] == 'mismatch'
    # Drop the final support packet: even equal reconstructed PCs cannot earn a match.
    csv_packets = tmp_path / 'native_input.te_inst'
    lines = csv_packets.read_text().splitlines()
    truncated = tmp_path / 'truncated.te_inst'
    truncated.write_text('\n'.join(lines[:-1]) + '\n')
    with pytest.raises(ValueError, match='final trace-disabled'):
        etrace.decode(root, truncated, static, ucf, toolchain=TOOLCHAIN)
    import csv
    with csv_packets.open() as stream:
        reader = csv.DictReader(stream)
        fields, packets = reader.fieldnames, list(reader)
    packets[-1]['qual_status'] = '2'
    lost = tmp_path / 'lost.te_inst'
    with lost.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(packets)
    with pytest.raises(ValueError, match='trace loss'):
        etrace.decode(root, lost, static, ucf, toolchain=TOOLCHAIN)
    raw = tmp_path / 'truncated.te_inst_raw'
    raw.write_bytes((tmp_path / 'native_input.te_inst_raw').read_bytes()[:-1])
    with pytest.raises(ValueError):
        etrace.decode(root, raw, static, ucf, toolchain=TOOLCHAIN)



@pytest.mark.parametrize('responses,error', [([2], RuntimeError), ([1], RuntimeError),
                                           ([3, 0, 0, 3, 0, 0], TimeoutError)])
def test_dmi_failure_and_busy_bound(responses, error):
    dmi = RemoteDMI.__new__(RemoteDMI)
    dmi.abits, dmi.idle, dmi.retries = 7, 0, 2
    scans = iter(responses)
    dmi.scan = lambda *args: next(scans)
    dmi.clock = lambda *args: 0
    dmi.ir = lambda *args: None
    # First scan queues a request; the next scan carries its status.
    original = dmi.scan
    first = [True]
    def scan(*args):
        if first[0]:
            first[0] = False
            return 0
        return original(*args)
    dmi.scan = scan
    with pytest.raises(error):
        dmi.access(0x11)


def test_dmi_busy_retries_request():
    dmi = RemoteDMI.__new__(RemoteDMI)
    dmi.abits, dmi.idle, dmi.retries = 7, 0, 2
    calls = []
    # Queue, busy response, DTMCS reset, retry request, successful response.
    responses = iter([0, 3, 0, 0, 0x1234 << 2])
    dmi.scan = lambda value, bits: (calls.append((value, bits)), next(responses))[1]
    dmi.clock = lambda *args: 0
    irs = []
    dmi.ir = irs.append
    assert dmi.access(0x11) == 0x1234
    assert irs == [0x10, 0x11]
    assert calls[0] == calls[3]
    assert calls[2] == (1 << 16, 32)


def c2(path, *, end=True):
    import json
    row = {k: '0x0' for k in 'pc pc_next insn rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata'.split()}
    row.update({k: 0 for k in 'order cycle mode rs1 rs2 rd mem_rmask mem_wmask'.split()})
    row.update({k: False for k in 'trap intr halt mem_fault'.split()})
    row.update(pc='0x1000', pc_next='0x1004', insn='0x13', mode=3)
    records = [dict(schema='rvw.rvfi/1', xlen=64, isa='rv64imac', core='fixture', config='fixture', elf='fixture'), row]
    if end:
        records.append(dict(event='end', cycle=1, status='pass'))
    path.write_text('\n'.join(json.dumps(r) for r in records) + '\n')


def test_c2_completion_and_cli(tmp_path, capsys):
    from rvw.cli import main
    path, output = tmp_path / 'c2.jsonl', tmp_path / 'input.csv'
    c2(path, end=False)
    rows, complete = etrace.retirement(path)
    assert len(rows) == 1 and not complete
    assert main(['debug', 'ingress', '--rvfi', str(path), '--out', str(output)]) == 3
    assert not output.exists()
    c2(path)
    assert main(['debug', 'ingress', '--rvfi', str(path), '--out', str(output)]) == 0
    assert output.is_file()
    args = ['debug', 'etrace']
    for name in ('reference', 'packets', 'static-config', 'user-config', 'toolchain', 'rvfi', 'out'):
        args += ['--' + name, str(path if name == 'rvfi' else tmp_path / name)]
    assert main(args) == 3
    import json
    assert json.loads((tmp_path / 'out').read_text())['status'] == 'inconclusive'
