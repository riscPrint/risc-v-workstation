"""RTL trace-ingress check against C2 (no native tools)."""
import csv

import pytest

from rvw.debug import etrace, etrace_flow as ef, ingress_check as ic

from test_debug_ntrace import run_c2

pytestmark = pytest.mark.fast


def write_ingress(path, entries):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, etrace.INGRESS)
        writer.writeheader()
        writer.writerows(entries)


def c2_ingress(rvfi):
    rows, _, xlen = ef.retirement(rvfi)
    return ef.ingress_rows(rows, xlen=xlen)


def test_matching_ingress_gives_match_and_ntrace_flow(tmp_path):
    rvfi = tmp_path / 'c2.jsonl'
    code = run_c2(rvfi)
    entries = c2_ingress(rvfi)
    assert {e['itype_0'] for e in entries} >= {ef.EXCEPTION, ef.TAKEN, ef.NOT_TAKEN, ef.UNINFERABLE}
    write_ingress(tmp_path / 'te_ingress.csv', entries)
    result = ic.check(tmp_path / 'te_ingress.csv', rvfi, code)
    assert result['ingress'] == {'status': 'match', 'rows': len(entries)}
    assert result['ntrace']['status'] == 'flow_match', result['ntrace']
    assert result['status'] == 'match'


def test_wrong_branch_outcome_is_a_mismatch(tmp_path):
    rvfi = tmp_path / 'c2.jsonl'
    code = run_c2(rvfi)
    entries = c2_ingress(rvfi)
    index = next(i for i, e in enumerate(entries) if e['itype_0'] == ef.TAKEN)
    entries[index] = {**entries[index], 'itype_0': ef.NOT_TAKEN}
    write_ingress(tmp_path / 'te_ingress.csv', entries)
    result = ic.check(tmp_path / 'te_ingress.csv', rvfi, code)
    assert result['ingress']['status'] == 'mismatch'
    assert result['ingress']['first_difference'] == index and result['ingress']['fields'] == ['itype_0']
    assert result['status'] == 'mismatch'


def test_missing_rows_and_empty_ingress_never_match(tmp_path):
    rvfi = tmp_path / 'c2.jsonl'
    code = run_c2(rvfi)
    entries = c2_ingress(rvfi)
    write_ingress(tmp_path / 'short.csv', entries[:-3])
    short = ic.check(tmp_path / 'short.csv', rvfi, code)
    assert short['ingress']['status'] == 'mismatch' and short['status'] == 'mismatch'
    write_ingress(tmp_path / 'empty.csv', [])
    empty = ic.check(tmp_path / 'empty.csv', rvfi, code)
    assert empty['ingress']['status'] == 'mismatch' and empty['ingress']['actual_rows'] == 0


def test_trap_event_without_trapping_row_is_rebuilt_only_with_code(tmp_path):
    import json
    from rvw.debug import ntrace
    rvfi = tmp_path / 'c2.jsonl'
    segments = run_c2(rvfi)
    full, _, xlen = ef.retirement(rvfi)
    lines = [json.loads(l) for l in rvfi.read_text().splitlines()]
    stripped = tmp_path / 'stripped.jsonl'
    kept, order = [], 0
    for r in lines:
        if r.get('trap'):
            continue
        if 'order' in r:
            r = {**r, 'order': order}
            order += 1
        kept.append(r)
    stripped.write_text(''.join(json.dumps(r) + '\n' for r in kept))
    with pytest.raises(ValueError):
        ef.retirement(stripped)
    rebuilt, complete, _ = ef.retirement(stripped, code=ntrace.Code(segments))
    keys = ('pc', 'pc_next', 'trap', 'exc', 'mode')
    assert [{k: r.get(k) for k in keys} for r in rebuilt] == [{k: r.get(k) for k in keys} for r in full]
    assert complete and sum(r.get('rebuilt', False) for r in rebuilt) == sum(bool(r.get('trap')) for r in full) > 0
