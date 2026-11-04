"""Pinned upstream baseline E-Trace decoder and exact retirement-PC comparison."""
import configparser
import csv
import hashlib
import os
import re
from pathlib import Path
import sys
import tempfile

from rvw.common.proc import run_group
from rvw.common.riscv import decode as decode_instruction
from rvw.cosim.trace import Trace

REFERENCE_REV = 'ffb6bb721f3de4e8ed9ee6d5acd52dd90df34670'
REFERENCE_URL = 'https://github.com/riscv-non-isa/riscv-trace-spec'
INGRESS = ['itype_0', 'cause', 'tval', 'priv', 'iaddr_0', 'context', 'ctype',
           'iretire_0', 'ilastsize_0']


def verify_reference(root):
    root = Path(root).resolve()
    rev = run_group(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture=True, timeout=10)
    dirty = run_group(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=all',
                       '--', 'referenceFlow/scripts'], capture=True, timeout=10)
    if rev.returncode or rev.stdout.strip() != REFERENCE_REV or dirty.returncode or dirty.stdout.strip():
        raise ValueError(f'need clean reference scripts at {REFERENCE_REV}')
    return root


def retirement(path, *, require_rv64=False):
    try:
        trace = Trace(path)
    except StopIteration as exc:
        raise ValueError('empty C2 stream') from exc
    try:
        if require_rv64 and trace.header['xlen'] != 64:
            raise ValueError('encoder ingress profile requires RV64')
        if trace.multihart:
            raise ValueError('select one hart before E-Trace comparison')
        rows = list(trace)
    finally:
        trace.close()
    complete = bool(rows and rows[-1].get('event') == 'end'
                    and rows[-1].get('status') == 'pass')
    return [r for r in rows if 'event' not in r], complete


def ingress(rows, path, *, xlen=64):
    """Export the baseline single-retire encoder port. Unsupported semantics fail closed.

    This does not encode packets. The core encoder, or upstream reference encoder,
    consumes this CSV. Trap/context ingress requires an adapter with explicit causes.
    """
    if not rows:
        raise ValueError('empty retirement stream')
    with Path(path).open('w') as output:
        writer = csv.writer(output)
        writer.writerow(INGRESS)
        for r in rows:
            if r.get('trap') or r.get('intr') or r.get('mode') != 3:
                raise ValueError('baseline ingress supports machine mode without traps only')
            pc, next_pc, insn = r['pc'], r['pc_next'], r['insn']
            instruction = decode_instruction(insn, xlen)
            if instruction.mnemonic == 'unknown' or instruction.mnemonic in ('mret', 'sret', 'dret'):
                raise ValueError('unsupported instruction in baseline ingress')
            kind = 0
            if instruction.cls == 'branch':
                kind = 4 if next_pc == pc + instruction.length else 5
            elif instruction.mnemonic in ('jalr', 'c.jr', 'c.jalr'):
                kind = 6
            writer.writerow([kind, 0, 0, r['mode'], f'{pc:x}', 0, 0, 1,
                             int(instruction.length == 4)])


def read_pcs(path):
    values = []
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        if len(fields) != 1 or not re.fullmatch(r'[0-9a-fA-F]+', fields[0]):
            raise ValueError('decoded trace requires one hexadecimal PC per line')
        value = int(fields[0], 16)
        if value < 0 or value >= 1 << 64 or value & 1:
            raise ValueError('invalid decoded PC')
        values.append(value)
    return values


def compare(decoded, expected, *, complete, loss=False):
    count = min(len(decoded), len(expected))
    mismatch = next((i for i in range(count) if decoded[i] != expected[i]), None)
    if mismatch is None and len(decoded) != len(expected):
        mismatch = count
    # A gap poisons the whole window. No guessed recovery or prefix match.
    if loss or not complete or not decoded or not expected:
        status = 'inconclusive'
    elif mismatch is not None:
        status = 'mismatch'
    else:
        status = 'flow_match'
    return {'status': status, 'scope': 'retirement-pc-sequence',
            'decoded_count': len(decoded), 'expected_count': len(expected),
            'first_difference': mismatch, 'complete': complete, 'loss': loss}


def decode(root, packets, static_config, user_config, *, toolchain, timeout=30):
    """Decode .te_inst CSV or .te_inst_raw with no oracle PC input to the decoder."""
    root = verify_reference(root)
    packets = Path(packets).resolve()
    static_config, user_config = Path(static_config).resolve(), Path(user_config).resolve()
    cfg = configparser.ConfigParser()
    try:
        cfg.read(user_config)
    except configparser.Error as exc:
        raise ValueError('invalid E-Trace user configuration') from exc
    # Upstream resolves object-files against cwd; require absolute ELF paths.
    objects = cfg['required']['object-files'].split()
    if not objects or any(not Path(p).is_absolute() or not Path(p).is_file() for p in objects):
        raise ValueError('object-files must contain existing absolute ELF paths')
    objdump = Path(toolchain).resolve() / 'bin/riscv64-unknown-elf-objdump'
    if not objdump.is_file():
        raise ValueError('missing native RISC-V objdump')
    env = {**os.environ, 'RISCV_TOOLCHAIN': str(Path(toolchain).resolve()), 'PYTHONDONTWRITEBYTECODE': '1'}
    env.pop('PYTHONOPTIMIZE', None)  # The reference uses assertions for packet validation.
    with tempfile.TemporaryDirectory(prefix='rvw-etrace-') as tmp:
        csv_packets = packets
        if packets.suffix == '.te_inst_raw':
            unpack = run_group([sys.executable, str(root / 'referenceFlow/scripts/te_inst_deserialiser.py'),
                                '-c', str(static_config), '-u', str(user_config), str(packets)],
                               cwd=tmp, env=env, timeout=timeout, capture=True)
            if unpack.returncode or unpack.timed_out:
                raise ValueError('raw E-Trace packet validation failed')
            csv_packets = Path(tmp) / (packets.stem + '.te_inst_csv')
        with csv_packets.open() as packet_file:
            packet_rows = list(csv.DictReader(packet_file))
        if not packet_rows:
            raise ValueError('empty packet stream')
        # Report the whole window as unknown after explicit encoder trace loss.
        # Recovery is not certified by this baseline adapter.
        if any(p.get('qual_status') == '2' for p in packet_rows):
            raise ValueError('encoder trace loss: reconstruction window is unknown')
        last = packet_rows[-1]
        if not (last.get('format') == '3' and last.get('subformat') == '3'
                and last.get('ienable') == '0' and last.get('qual_status') in ('1', '3')):
            raise ValueError('missing final trace-disabled support packet')
        result = run_group([sys.executable, str(root / 'referenceFlow/scripts/decoder_model.py'),
                            '-c', str(static_config), '-u', str(user_config), '-i', str(packets)],
                           cwd=tmp, env=env, timeout=timeout, capture=True)
        if result.returncode or result.timed_out:
            raise ValueError('reference decoder failed: ' + (result.stdout or '')[-1500:]
                             + (result.stderr or '')[-1500:])
        output = Path(tmp) / (packets.stem + '.decoder.trace')
        pcs = read_pcs(output)
    return pcs, {'decoder_rev': REFERENCE_REV,
                 'packets_sha256': hashlib.sha256(packets.read_bytes()).hexdigest(),
                 'elf_sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in objects},
                 'static_sha256': hashlib.sha256(static_config.read_bytes()).hexdigest(),
                 'user_sha256': hashlib.sha256(user_config.read_bytes()).hexdigest()}
