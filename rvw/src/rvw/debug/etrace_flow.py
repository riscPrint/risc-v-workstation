"""E-Trace flow checks beyond the baseline profile: traps, trap returns and privilege in
the encoder ingress, packet-level comparison with the pinned reference encoder, loss
windows with resynchronization, and trace filters.

The reference encoder and decoder are the pinned upstream Python models (see etrace.py).
This module never guesses execution inside a lost or filtered window.
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile

from rvw.common.proc import run_group
from rvw.common.riscv import decode as decode_instruction
from rvw.cosim.trace import Trace

from . import etrace

ITYPE_NONE, EXCEPTION, INTERRUPT, TRAP_RETURN, NOT_TAKEN, TAKEN, UNINFERABLE = 0, 1, 2, 3, 4, 5, 6
RETURNS = {'mret', 'sret', 'uret'}
JUMPS = {'jalr', 'c.jr', 'c.jalr'}


# -- C2 with trap causes -------------------------------------------------------------
def retirement(path):
    """C2 retirement rows. Exception rows get `exc=(cause, tval)`; the first row after an
    interrupt gets `irq=cause`. Returns (rows, complete, xlen)."""
    try:
        trace = Trace(path)
    except StopIteration as exc:
        raise ValueError('empty C2 stream') from exc
    try:
        if trace.multihart:
            raise ValueError('select one hart before trace comparison')
        xlen = trace.header['xlen']
        records = list(trace)
    finally:
        trace.close()
    rows, pending_irq = [], None
    for record in records:
        if record.get('event') == 'trap':
            if record['intr']:
                pending_irq = record['cause'] & ~(1 << (xlen - 1))
            else:
                trapped = next((r for r in reversed(rows) if r.get('trap')), None)
                if trapped is None or 'exc' in trapped:
                    raise ValueError('trap event without a trapping instruction')
                trapped['exc'] = (record['cause'], record['tval'])
            continue
        if 'event' in record:
            continue
        row = dict(record)
        if pending_irq is not None:
            row['irq'] = pending_irq
            pending_irq = None
        rows.append(row)
    for row in rows:
        if row.get('trap') and 'exc' not in row:
            raise ValueError(f'trapping instruction at 0x{row["pc"]:x} has no trap event cause')
    complete = bool(records and records[-1].get('event') == 'end' and records[-1].get('status') == 'pass')
    return rows, complete, xlen


def ingress_rows(rows, *, xlen=64):
    """Encoder ingress (single retirement) for exceptions, interrupts, trap returns and privilege."""
    if not rows:
        raise ValueError('empty retirement stream')
    out = []
    previous = None
    for row in rows:
        if row['mode'] not in (0, 1, 3):
            raise ValueError('unsupported privilege mode in ingress')
        if 'irq' in row and previous is not None:
            # Exception-only entry: nothing retires; the hart takes the interrupt before pc_next.
            out.append(_entry(INTERRUPT, row['irq'], 0, previous['mode'], previous['pc_next'], 0, 0))
        instruction = decode_instruction(row['insn'], xlen)
        if instruction.mnemonic == 'unknown':
            raise ValueError(f'unknown instruction at 0x{row["pc"]:x}')
        size = int(instruction.length == 4)
        if row.get('trap'):
            cause, tval = row['exc']
            # Exception-only entry at the trapping pc: the trapping instruction does not retire.
            out.append(_entry(EXCEPTION, cause, tval, row['mode'], row['pc'], 0, size))
            previous = row
            continue
        kind = ITYPE_NONE
        if instruction.cls == 'branch':
            kind = NOT_TAKEN if row['pc_next'] == row['pc'] + instruction.length else TAKEN
        elif instruction.mnemonic in JUMPS:
            kind = UNINFERABLE
        elif instruction.mnemonic in RETURNS:
            # The pinned baseline encoder (itype_width_p=3) treats only itype 6 as an uninferable
            # discontinuity, and its decoder treats xRET as uninferable: report xRET as itype 6.
            kind = UNINFERABLE
        elif instruction.mnemonic == 'dret':
            raise ValueError('dret is not encoder ingress')
        out.append(_entry(kind, 0, 0, row['mode'], row['pc'], 1, size))
        previous = row
    return out


def _entry(itype, cause, tval, priv, address, retire, size):
    return {'itype_0': itype, 'cause': cause, 'tval': f'{tval:x}', 'priv': priv, 'iaddr_0': f'{address:x}',
            'context': 0, 'ctype': 0, 'iretire_0': retire, 'ilastsize_0': size}


def write_ingress(entries, path):
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, etrace.INGRESS)
        writer.writeheader()
        writer.writerows(entries)


def expected_pcs(rows):
    """PCs the decoder reports: retired instructions. A trapping instruction does not retire."""
    return [r['pc'] for r in rows if not r.get('trap')]


# -- reference encoder ----------------------------------------------------------------
def encode(root, entries, static_config, user_config, *, timeout=60):
    """Run the pinned upstream encoder. Returns (te_inst rows, raw bytes)."""
    root = etrace.verify_reference(root)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    env.pop('PYTHONOPTIMIZE', None)
    import configparser
    with tempfile.TemporaryDirectory(prefix='rvw-etrace-enc-') as tmp:
        # The upstream encoder reads FILE-STEM_input and writes into its working directory.
        ingress = Path(tmp) / 'encoder_input'
        write_ingress(entries, ingress)
        user = configparser.ConfigParser()
        user.read(user_config)
        user['required']['file-stem'] = str(Path(tmp) / 'encoder')
        ucf = Path(tmp) / 'encoder.ucf'
        with ucf.open('w') as stream:
            user.write(stream)
        result = run_group([sys.executable, str(root / 'referenceFlow/scripts/encoder_model.py'),
                            '-c', str(Path(static_config).resolve()), '-u', str(ucf)],
                           cwd=tmp, env=env, timeout=timeout, capture=True)
        if result.returncode or result.timed_out:
            raise ValueError('reference encoder failed: ' + (result.stdout or '')[-800:] + (result.stderr or '')[-800:])
        rows = read_packets(Path(tmp) / 'encoder_input.te_inst')
        raw = (Path(tmp) / 'encoder_input.te_inst_raw').read_bytes()
    return rows, raw


def read_packets(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream))


def write_packets(rows, path):
    if not rows:
        raise ValueError('no packets')
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


PACKET_FIELDS = ('format', 'subformat', 'branch', 'privilege', 'address', 'ecause', 'interrupt', 'thaddr',
                 'tvalepc', 'branches', 'branch_map', 'notify', 'updiscon', 'irreport', 'irdepth', 'ienable',
                 'encoder_mode', 'qual_status', 'ioptions')


def compare_packets(actual, expected):
    """Field-by-field te_inst comparison. Fields absent or '_' on both sides are ignored."""
    count = min(len(actual), len(expected))
    for index in range(count):
        for field in PACKET_FIELDS:
            a = _field(actual[index], field)
            e = _field(expected[index], field)
            if a != e:
                return {'status': 'mismatch', 'scope': 'te_inst-packets', 'first_difference': index,
                        'field': field, 'actual': a, 'expected': e,
                        'actual_count': len(actual), 'expected_count': len(expected)}
    if len(actual) != len(expected):
        return {'status': 'mismatch', 'scope': 'te_inst-packets', 'first_difference': count, 'field': None,
                'actual_count': len(actual), 'expected_count': len(expected)}
    if not actual:
        return {'status': 'inconclusive', 'scope': 'te_inst-packets', 'reason': 'empty packet streams'}
    return {'status': 'packet_match', 'scope': 'te_inst-packets', 'packets': len(actual)}


def _field(row, name):
    value = row.get(name)
    return None if value in (None, '', '_') else value


# -- decoding with loss windows ---------------------------------------------------------
def _is_sync_start(row):
    return row.get('format') == '3' and row.get('subformat') in ('0', '1')


def _is_support_end(row):
    return row.get('format') == '3' and row.get('subformat') == '3' and row.get('qual_status') in ('1', '2', '3')


def segments(rows, losses=(), *, ioptions='0'):
    """Split a packet stream into decodable segments.

    `losses` are packet indices known to follow a gap (dropped packets, overflow, buffer wrap).
    A support packet with qual_status 2 (trace lost) also ends a segment. After a gap,
    packets are skipped until a sync start (format 3, subformat 0). Each segment starts with
    the stream's support packet (it carries the decoder options), or a support packet with
    the declared `ioptions` when a wrap lost it. Returns (segments, skipped).
    """
    losses = set(losses)
    support = next((dict(r) for r in rows if r.get('format') == '3' and r.get('subformat') == '3'
                    and r.get('ienable') == '1' and r.get('qual_status') == '0'), None)
    if support is None and rows:
        support = {k: '_' for k in rows[0]}
        support.update(format='3', subformat='3', ienable='1', encoder_mode='0', qual_status='0', ioptions=ioptions)
    result, current, skipped = [], [], 0
    synced = False
    for index, row in enumerate(rows):
        if index in losses:
            if current:
                result.append(current)
            current, synced = [], False
        if not synced:
            if row.get('format') == '3' and row.get('subformat') == '0':
                synced = True
                current = [support]
            else:
                if not (row is rows[0] and row.get('subformat') == '3'):
                    skipped += 1
                continue
        current.append(row)
        if row.get('format') == '3' and row.get('subformat') == '3' and row.get('qual_status') in ('1', '2', '3'):
            result.append(current)
            current, synced = [], False
    if current:
        result.append(current)
    return result, skipped


def close_segment(segment):
    """Make a segment decodable. Returns (rows, ended_normally).

    A segment cut by a gap gets a trace-ended support packet. A trace-lost support packet
    becomes trace-ended: the gap is already accounted for by the segmentation. The decoder
    reports nothing after the last packet, so no execution after the gap is invented.
    """
    last = segment[-1]
    if last.get('format') == '3' and last.get('subformat') == '3' and last.get('qual_status') in ('1', '3'):
        return segment, True
    closing = {key: '_' for key in last}
    closing.update(format='3', subformat='3', ienable='0', encoder_mode='0', qual_status='1',
                   ioptions=segment[0].get('ioptions', '0'))
    if last.get('format') == '3' and last.get('subformat') == '3':
        return segment[:-1] + [closing], False
    return segment + [closing], False


def decode_rows(root, rows, static_config, user_config, *, toolchain, timeout=60):
    with tempfile.TemporaryDirectory(prefix='rvw-etrace-seg-') as tmp:
        path = Path(tmp) / 'segment.te_inst'
        write_packets(rows, path)
        pcs, identity = etrace.decode(root, path, static_config, user_config, toolchain=toolchain, timeout=timeout)
    return pcs


def align(window, expected, start):
    """First index >= start where `window` is a contiguous run of `expected`, or None."""
    if not window:
        return None
    first = window[0]
    for index in range(start, len(expected) - len(window) + 1):
        if expected[index] == first and expected[index:index + len(window)] == window:
            return index
    return None


def windows(decoded_segments, expected, *, leading_gap=False):
    """Align decoded segments with C2 in order. Gaps between segments are unknown windows.
    Without a leading gap the first segment must start at the first retirement."""
    report, cursor = [], 0
    for number, (pcs, _closed) in enumerate(decoded_segments):
        at = align(pcs, expected, cursor)
        if at is None or (number == 0 and not leading_gap and at != 0):
            report.append({'segment': number, 'status': 'mismatch', 'decoded': len(pcs), 'start': at})
            continue
        if at > cursor:
            report.append({'status': 'unknown', 'start': cursor, 'count': at - cursor})
        report.append({'segment': number, 'status': 'observed', 'start': at, 'count': len(pcs)})
        cursor = at + len(pcs)
    if cursor < len(expected):
        report.append({'status': 'unknown', 'start': cursor, 'count': len(expected) - cursor})
    return report, sum(w['count'] for w in report if w['status'] == 'observed')


def verdict(report, expected, *, complete, gaps):
    """flow_match: one gap-free stream equals C2. partial_match: every observed window equals
    its C2 window and lost windows stay unknown. Without a known gap, a missing span is a mismatch."""
    if any(w['status'] == 'mismatch' for w in report):
        return 'mismatch'
    observed = sum(w['count'] for w in report if w['status'] == 'observed')
    if not complete or not expected or not observed:
        return 'inconclusive'
    unknown = any(w['status'] == 'unknown' for w in report)
    if unknown and not gaps:
        return 'mismatch'
    return 'partial_match' if unknown else 'flow_match'


# -- loss injection (for campaigns against the reference) --------------------------------
def inject(rows, kind, at):
    """Return (rows, losses) with a fault injected at packet index `at`.

    drop: remove packet `at`. overflow: replace packet `at` with a trace-lost support packet.
    wrap: discard the packets before `at` (a circular buffer overwrote them).
    truncate: cut the stream after packet `at` (no closing support packet).
    """
    rows = [dict(r) for r in rows]
    if not 0 <= at < len(rows):
        raise ValueError('injection index out of range')
    if kind == 'drop':
        return rows[:at] + rows[at + 1:], [at]
    if kind == 'overflow':
        lost = {k: '_' for k in rows[at]}
        lost.update(format='3', subformat='3', ienable='1', encoder_mode='0', qual_status='2',
                    ioptions=rows[0].get('ioptions', '0'))
        return rows[:at] + [lost] + rows[at + 1:], [at + 1]
    if kind == 'wrap':
        return rows[at:], [0]
    if kind == 'truncate':
        return rows[:at + 1], []
    raise ValueError('kind must be drop, overflow, wrap or truncate')


# -- filters ---------------------------------------------------------------------------
def qualify(rows, spec):
    """Trace qualification per instruction. spec keys: privileges (list of modes),
    ranges (list of [lo, hi) address pairs to trace), exclude (ranges never traced),
    start/stop (addresses that switch tracing on/off, like trace-on/trace-off triggers)."""
    privileges = set(spec.get('privileges', (0, 1, 3)))
    ranges = [tuple(r) for r in spec.get('ranges', ())]
    exclude = [tuple(r) for r in spec.get('exclude', ())]
    start, stop = spec.get('start'), spec.get('stop')
    active = start is None
    flags = []
    for row in rows:
        if start is not None and row['pc'] == start:
            active = True
        ok = active and row['mode'] in privileges
        if ranges:
            ok = ok and any(lo <= row['pc'] < hi for lo, hi in ranges)
        if any(lo <= row['pc'] < hi for lo, hi in exclude):
            ok = False
        flags.append(ok)
        if stop is not None and row['pc'] == stop:
            active = False
    return flags


def qualified_windows(rows, flags):
    windows_, current = [], []
    for row, ok in zip(rows, flags):
        if ok:
            current.append(row)
        elif current:
            windows_.append(current)
            current = []
    if current:
        windows_.append(current)
    return windows_


def leaks(decoded, rows, flags):
    """Decoded PCs that belong only to unqualified (filtered or protected) execution."""
    allowed = {r['pc'] for r, ok in zip(rows, flags) if ok}
    hidden = {r['pc'] for r, ok in zip(rows, flags) if not ok} - allowed
    return sorted({pc for pc in decoded if pc in hidden or pc not in allowed})


def packet_addresses(rows, *, lsb=0):
    """Full addresses carried by sync packets (format 3), for retained-buffer leak checks.
    te_inst CSV addresses are hexadecimal, shifted right by iaddress_lsb_p."""
    return [int(r['address'], 16) << lsb
            for r in rows if r.get('format') == '3' and r.get('subformat') in ('0', '1')
            and r.get('address') not in (None, '', '_')]


def sha256(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def rows_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


# -- top level ---------------------------------------------------------------------------
def deserialise(root, raw, static_config, user_config, *, timeout=60):
    root = etrace.verify_reference(root)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    env.pop('PYTHONOPTIMIZE', None)
    with tempfile.TemporaryDirectory(prefix='rvw-etrace-raw-') as tmp:
        path = Path(tmp) / 'stream.te_inst_raw'
        path.write_bytes(Path(raw).read_bytes() if not isinstance(raw, bytes) else raw)
        result = run_group([sys.executable, str(root / 'referenceFlow/scripts/te_inst_deserialiser.py'),
                            '-c', str(Path(static_config).resolve()), '-u', str(Path(user_config).resolve()),
                            str(path)], cwd=tmp, env=env, timeout=timeout, capture=True)
        if result.returncode or result.timed_out:
            raise ValueError('raw E-Trace packet validation failed')
        return read_packets(Path(tmp) / 'stream.te_inst_csv')


def load_packets(root, path, static_config, user_config):
    path = Path(path)
    if path.suffix == '.te_inst_raw':
        return deserialise(root, path, static_config, user_config)
    return read_packets(path)


def expected_stream(root, rows, flags, static_config, user_config):
    """Reference packets and PCs for the qualified windows (each window: start sync .. end support)."""
    packets, pcs = [], []
    for window in qualified_windows(rows, flags):
        window_packets, _ = encode(root, ingress_rows(window), static_config, user_config)
        packets += window_packets
        pcs += expected_pcs(window)
    return packets, pcs


def decode_stream(root, packets, expected, static_config, user_config, *, toolchain, losses=()):
    losses = set(losses) | {i + 1 for i, r in enumerate(packets)
                            if r.get('format') == '3' and r.get('subformat') == '3' and r.get('qual_status') == '2'}
    segs, skipped = segments(packets, losses)
    decoded, errors = [], []
    for seg in segs:
        rows_, closed = close_segment(seg)
        try:
            decoded.append((decode_rows(root, rows_, static_config, user_config, toolchain=toolchain), closed))
        except ValueError as exc:
            errors.append(str(exc)[-300:])
            decoded.append(([], closed))
    first_sync = next((i for i, r in enumerate(packets) if r.get('format') == '3' and r.get('subformat') == '0'),
                      len(packets))
    leading = any(loss <= first_sync for loss in losses)
    report, observed = windows([d for d in decoded if d[0]], expected, leading_gap=leading)
    if errors:
        report.append({'status': 'mismatch', 'reason': 'segment decode failed', 'errors': errors})
    return report, decoded, sorted(losses), skipped


def check(root, rvfi, static_config, user_config, *, toolchain, packets=None, filter_spec=None, losses=()):
    rows, complete, xlen = retirement(rvfi)
    flags = qualify(rows, filter_spec or {})
    expected_packets, expected = expected_stream(root, rows, flags, static_config, user_config)
    result = {'scope': 'e-trace-baseline-flow', 'decoder_rev': etrace.REFERENCE_REV,
              'retired': len(rows), 'qualified': sum(flags), 'expected_packets': len(expected_packets),
              'rvfi_sha256': sha256(Path(rvfi).read_bytes()), 'complete': complete}
    if packets is None:
        result.update(status='no_checks', reason='no encoder packets given; expected stream only')
        return result, expected_packets
    actual = load_packets(root, packets, static_config, user_config)
    result['packets_sha256'] = sha256(Path(packets).read_bytes())
    result['packets'] = compare_packets(actual, expected_packets)
    report, decoded, all_losses, skipped = decode_stream(root, actual, expected, static_config, user_config,
                                                         toolchain=toolchain, losses=losses)
    result.update(windows=report, losses=all_losses, skipped_packets=skipped)
    hidden_pcs = leaks([pc for pcs, _ in decoded for pc in pcs], rows, flags)
    hidden_addresses = sorted({a for a in packet_addresses(actual)
                               if any(r['pc'] == a for r, ok in zip(rows, flags) if not ok)
                               and not any(r['pc'] == a for r, ok in zip(rows, flags) if ok)})
    if hidden_pcs or hidden_addresses:
        result.update(status='leak', leaked_pcs=[hex(p) for p in hidden_pcs],
                      leaked_addresses=[hex(a) for a in hidden_addresses])
    else:
        result['status'] = verdict(report, expected, complete=complete, gaps=bool(all_losses))
    return result, expected_packets


FAULTS = ('drop', 'overflow', 'wrap', 'truncate')


def loss_campaign(root, rvfi, static_config, user_config, *, toolchain, packets=None, positions=None):
    """Inject each fault kind at sampled packet positions and check recovery. Returns C3 tests."""
    rows, complete, xlen = retirement(rvfi)
    flags = [True] * len(rows)
    expected_packets, expected = expected_stream(root, rows, flags, static_config, user_config)
    base = load_packets(root, packets, static_config, user_config) if packets else expected_packets
    if len(base) < 4:
        raise ValueError('packet stream too short for a loss campaign')
    positions = positions or sorted({1, 2, len(base) // 3, len(base) // 2, len(base) - 3})
    tests = []
    for kind in FAULTS:
        for at in positions:
            if not 0 < at < len(base) - 1:
                continue
            damaged, losses = inject(base, kind, at)
            report, decoded, all_losses, skipped = decode_stream(root, damaged, expected, static_config,
                                                                 user_config, toolchain=toolchain, losses=losses)
            status = verdict(report, expected, complete=complete, gaps=bool(all_losses) or kind == 'truncate')
            unknown = sum(w['count'] for w in report if w['status'] == 'unknown')
            test = {'id': f'etrace.loss.{kind}.{at}', 'windows': report, 'unknown_instructions': unknown,
                    'skipped_packets': skipped}
            if status == 'mismatch':
                test.update(status='fail', signature=f'trace:loss:{kind}', message='an observed window disagrees with C2',
                            message_complete=True)
            elif status == 'partial_match':
                test['status'] = 'pass'
            elif status == 'flow_match':
                # A fault that loses nothing must still match exactly (for example a dropped
                # packet that only repeated known state). Report it, but it shows no recovery.
                test['status'] = 'pass'
                test['note'] = 'no instructions were lost by this fault'
            else:
                test.update(status='error', signature='inconclusive', inconclusive=status)
            tests.append(test)
    return tests
