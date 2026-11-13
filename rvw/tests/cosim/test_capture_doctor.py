import json
import pytest

pytestmark = pytest.mark.fast
from rvw.cosim.doctor import execute_json
from test_state import fixture
from test_csr_capability import csr_only


def write(tmp_path, header, row, end=True):
    path = tmp_path / 'trace.jsonl'
    rows = [header, row]
    if end:
        rows.append(dict(event='end', cycle=2, status='pass'))
    path.write_text('\n'.join(map(json.dumps, rows))+'\n')
    return path


def test_csr_capture_does_not_claim_fp(tmp_path):
    h, row, _ = csr_only()
    r = execute_json(trace=write(tmp_path, h, row), core='boom')
    assert r['status'] == 'inspected'
    assert r['compared'] is False
    assert r['instructions'] == 1 and r['trace_complete']
    assert r['comparisons']['csr_snapshot']['configured']
    assert not r['comparisons']['fp']['configured']
    assert not r['comparisons']['vector']['configured']
    assert r['csr_snapshot'] == ['0x300']


def test_strict_scope_and_incomplete_trace(tmp_path):
    h, row = fixture()
    r = execute_json(trace=write(tmp_path, h, row, False), core='boom', strict=True)
    assert r['status'] == 'inspected' and not r['trace_complete']
    assert r['conditional_masks'] == []
    assert r['synchronization_enabled'] == []
    assert r['comparisons']['fp']['configured']


def test_validate_records_and_isa(tmp_path):
    h, row = fixture()
    row['order'] = -1
    assert execute_json(trace=write(tmp_path, h, row), core='boom')['status'] == 'error'
    h['xlen'] = 32
    assert 'ISA/XLEN' in execute_json(trace=write(tmp_path, h, row), core='boom')['message']


def test_declared_masks_are_reported(tmp_path):
    from rvw.cosim.platform import Platform
    h, row = fixture()
    import rvw.cosim.platform as module
    from pathlib import Path
    p = json.loads((Path(module.__file__).with_name('configs')/'boom.json').read_text())
    p['csr_masks'] = {'0x301': '0x6'}
    path = tmp_path/'platform.json'
    path.write_text(json.dumps(p))
    r = execute_json(trace=write(tmp_path, h, row), platform=path)
    assert r['status'] == 'inspected', r
    assert any(m.get('csr') == '0x301' and m['mask'] == '0x6' for m in r['conditional_masks'])


def test_mcp_doctor_dispatches_without_a_job_argument(tmp_path):
    from rvw.cosim.doctor import mcp_tools
    from rvw.mcp.registry import Registry
    h, row = fixture()
    registry = Registry(mcp_tools(), sync_s=20)
    _, result, error = registry.call_json('cosim_doctor',
        {'trace': str(write(tmp_path, h, row)), 'core': 'boom'})
    assert not error, result
    assert result['status'] == 'inspected' and result['instructions'] == 1
    assert result['compared'] is False


@pytest.mark.parametrize('ended_harts,complete', [([0], False), ([0, 1], True)])
def test_multihart_completion(tmp_path, ended_harts, complete):
    header, row = fixture()
    header.update(harts=[0, 1], capabilities=['multihart', 'state'])
    rows = [header]
    for hart in (0, 1):
        rows.append(dict(event='reset', cycle=0, hart=hart, epoch=0))
    for hart in (0, 1):
        rows.append(dict(row, hart=hart, epoch=0, order='0'))
    for hart in ended_harts:
        rows.append(dict(event='hart_end', cycle=2, hart=hart, epoch=0, status='pass'))
    for sequence, record in enumerate(rows[1:]):
        record['capture_seq'] = str(sequence)
    path = tmp_path / 'multi.jsonl'
    path.write_text('\n'.join(map(json.dumps, rows)))
    result = execute_json(trace=path, core='boom')
    assert result['status'] == 'inspected', result
    assert result['trace_complete'] is complete
