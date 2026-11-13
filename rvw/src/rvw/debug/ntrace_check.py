"""N-Trace checks: expected stream from C2, message comparison, segmented decoding with loss
windows, loss campaign and filters. Vendor trace adapters (`rvw.trace-adapter/1`) configure
the codec and must pass their own known packet vectors before use.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import tomllib

from . import etrace_flow as ef, ntrace
from .profile import load_elf

ADAPTER_SCHEMA = 'rvw.trace-adapter/1'


class AdapterError(ValueError):
    pass


def load_adapter(path):
    """A vendor adapter: codec parameters, a cited specification, and known packet vectors.
    A vendor name alone is not evidence of format compatibility."""
    data = Path(path).read_bytes()
    raw = tomllib.loads(data.decode())
    if raw.get('schema') != ADAPTER_SCHEMA:
        raise AdapterError(f'adapter schema must be {ADAPTER_SCHEMA}')
    unknown = set(raw) - {'schema', 'name', 'vendor', 'codec', 'specification', 'license', 'ntrace', 'vectors'}
    if unknown:
        raise AdapterError(f'unknown adapter keys: {", ".join(sorted(unknown))}')
    if raw.get('codec') != ntrace.CODEC:
        raise AdapterError(f'adapter codec must be {ntrace.CODEC}')
    for key in ('name', 'specification', 'license'):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise AdapterError(f'adapter needs a non-empty {key}')
    vectors = raw.get('vectors') or []
    if not vectors:
        raise AdapterError('adapter needs known packet vectors; a vendor name is not evidence of compatibility')
    params = ntrace.normalize(raw.get('ntrace', {}))
    report = verify_vectors(vectors, params)
    return {'name': raw['name'], 'vendor': raw.get('vendor'), 'specification': raw['specification'],
            'params': params, 'vectors': report, 'verified': all(v['status'] == 'pass' for v in report),
            'sha256': hashlib.sha256(data).hexdigest()}


def verify_vectors(vectors, params):
    report = []
    for index, vector in enumerate(vectors):
        try:
            data = bytes.fromhex(vector['bytes'].replace(' ', ''))
            want = [_normal(m) for m in vector['messages']]
            got, rest = ntrace.unpack(data, params)
            got = [m.as_dict() for m in got]
            packed = ntrace.pack([ntrace.Message(m['tcode'], {k: v for k, v in m.items() if k not in ('tcode', 'src')},
                                                 m.get('src', 0)) for m in want], params)
            ok = got == want and not rest and packed == data
            report.append({'vector': index, 'status': 'pass' if ok else 'fail',
                           'decoded': got if not ok else None})
        except (KeyError, ValueError, TypeError) as exc:
            report.append({'vector': index, 'status': 'fail', 'error': str(exc)})
    return report


def _normal(message):
    message = dict(message)
    message.setdefault('src', 0)
    fields = ntrace.LAYOUT[message['tcode']]
    for name, _ in fields:
        message.setdefault(name, 0)
    return message


def params_for(profile=None, adapter=None):
    if adapter is not None:
        if not adapter['verified']:
            raise AdapterError(f'adapter {adapter["name"]} failed its packet vectors')
        return adapter['params']
    return ntrace.normalize(profile)


def expected(rows, flags, params, xlen):
    windows = ef.qualified_windows(rows, flags)
    messages = ntrace.encode_windows(windows, params, xlen=xlen)
    pcs = [pc for w in windows for pc in ef.expected_pcs(w)]
    return messages, pcs


def compare_messages(actual, expected_messages):
    a = [m.as_dict() for m in actual]
    e = [m.as_dict() for m in expected_messages]
    for index, (x, y) in enumerate(zip(a, e)):
        if x != y:
            return {'status': 'mismatch', 'first_difference': index, 'actual': x, 'expected': y,
                    'actual_count': len(a), 'expected_count': len(e)}
    if len(a) != len(e):
        return {'status': 'mismatch', 'first_difference': min(len(a), len(e)),
                'actual_count': len(a), 'expected_count': len(e)}
    return {'status': 'message_match', 'messages': len(a)} if a else {'status': 'inconclusive'}


def decode_stream(messages, code, params, expected_pcs, *, xlen=64, losses=()):
    losses = set(losses)
    stream = []
    for index, message in enumerate(messages):
        if index in losses:
            stream.append(ntrace.Message('Error', {'etype': params['etype_overflow'], 'ecode': 0}))
        stream.append(message)
    gaps = bool(losses) or any(m.name == 'Error' for m in messages)
    segments = ntrace.decode(stream, code, params, xlen=xlen)
    decoded = [(pcs, clean) for pcs, clean, _ in segments]
    # After any gap the first observed window may start late: a loss can come before the first
    # decoded instruction. Without a gap it must start at the first retirement.
    report, _ = ef.windows(decoded, expected_pcs, leading_gap=gaps)
    for pcs, clean, reason in segments:
        if reason.startswith('decode failure'):
            report.append({'status': 'mismatch', 'reason': reason})
    return report, segments, gaps


def check(rvfi, elf, *, packets=None, profile=None, adapter=None, filter_spec=None, losses=()):
    rows, complete, xlen = ef.retirement(rvfi)
    params = params_for(profile, adapter)
    flags = ef.qualify(rows, filter_spec or {})
    want_messages, want_pcs = expected(rows, flags, params, xlen)
    data = ntrace.pack(want_messages, params)
    result = {'scope': 'n-trace-flow', 'codec': ntrace.CODEC, 'mode': params['mode'], 'retired': len(rows),
              'qualified': sum(flags), 'expected_messages': len(want_messages), 'complete': complete,
              'rvfi_sha256': ef.sha256(Path(rvfi).read_bytes())}
    if adapter is not None:
        result['adapter'] = {'name': adapter['name'], 'sha256': adapter['sha256']}
    if packets is None:
        result.update(status='no_checks', reason='no encoder capture given; expected stream only')
        return result, data
    capture = Path(packets).read_bytes()
    result['packets_sha256'] = ef.sha256(capture)
    try:
        actual, rest = ntrace.unpack(capture, params)
    except ValueError as exc:
        result.update(status='mismatch', reason=f'malformed capture: {exc}')
        return result, data
    result['messages'] = compare_messages(actual, want_messages)
    result['trailing_bytes'] = rest
    code = ntrace.Code(_segments(elf, xlen))
    report, segments, gaps = decode_stream(actual, code, params, want_pcs, xlen=xlen, losses=losses)
    result['windows'] = report
    decoded = [pc for pcs, _, _ in segments for pc in pcs]
    hidden = ef.leaks(decoded, rows, flags)
    addresses = [m.fields['faddr'] << 1 for m in actual if m.name == 'ProgTraceSync']
    hidden_rows = {r['pc'] for r, ok in zip(rows, flags) if not ok} - {r['pc'] for r, ok in zip(rows, flags) if ok}
    leaked_addresses = sorted(a for a in addresses if a in hidden_rows)
    if hidden or leaked_addresses:
        result.update(status='leak', leaked_pcs=[hex(p) for p in hidden], leaked_addresses=[hex(a) for a in leaked_addresses])
    else:
        result['status'] = ef.verdict(report, want_pcs, complete=complete, gaps=gaps or bool(rest))
        if result['status'] == 'flow_match' and (rest or not segments or not segments[-1][1]):
            result.update(status='inconclusive', reason='the capture does not end with a stop message')
    return result, data


def _segments(elf, xlen):
    """An ELF path, or (address, bytes) code segments."""
    if isinstance(elf, (str, Path)):
        return load_elf(elf, xlen)
    return list(elf)


def inject(messages, kind, at):
    """drop / overflow (an Error message) / wrap (lose the prefix) / truncate (cut the end)."""
    messages = list(messages)
    if not 0 <= at < len(messages):
        raise ValueError('injection index out of range')
    if kind == 'drop':
        return messages[:at] + messages[at + 1:], [at]
    if kind == 'overflow':
        return messages[:at] + [ntrace.Message('Error', {'etype': 0, 'ecode': 0})] + messages[at + 1:], []
    if kind == 'wrap':
        return messages[at:], [0]
    if kind == 'truncate':
        return messages[:at + 1], []
    raise ValueError('kind must be drop, overflow, wrap or truncate')


def loss_campaign(rvfi, elf, *, profile=None, adapter=None, positions=None):
    rows, complete, xlen = ef.retirement(rvfi)
    params = params_for(profile, adapter)
    messages, pcs = expected(rows, [True] * len(rows), params, xlen)
    code = ntrace.Code(_segments(elf, xlen))
    positions = positions or sorted({1, 2, len(messages) // 3, len(messages) // 2, len(messages) - 3})
    tests = []
    syncs = [i for i, m in enumerate(messages) if m.name == 'ProgTraceSync']
    first_flow = next(i for i, m in enumerate(messages) if m.name not in ('ProgTraceSync', 'Ownership'))
    for kind in ef.FAULTS:
        for at in positions:
            if not 0 < at < len(messages) - 1:
                continue
            # Skip positions that cannot show recovery: no later sync, or nothing decodable left.
            if kind != 'truncate' and not any(i > at for i in syncs) or kind == 'truncate' and at < first_flow:
                continue
            damaged, losses = inject(messages, kind, at)
            report, _, gaps = decode_stream(damaged, code, params, pcs, xlen=xlen, losses=losses)
            status = ef.verdict(report, pcs, complete=complete, gaps=gaps or kind == 'truncate')
            unknown = sum(w['count'] for w in report if w['status'] == 'unknown')
            test = {'id': f'ntrace.{params["mode"]}.loss.{kind}.{at}', 'windows': report, 'unknown_instructions': unknown}
            if status == 'mismatch':
                test.update(status='fail', signature=f'trace:ntrace-loss:{kind}',
                            message='an observed window disagrees with C2', message_complete=True)
            elif status in ('partial_match', 'flow_match'):
                test['status'] = 'pass'
                if status == 'flow_match':
                    test['note'] = 'no instructions were lost by this fault'
            else:
                test.update(status='error', signature='inconclusive', inconclusive=status)
            tests.append(test)
    return tests
