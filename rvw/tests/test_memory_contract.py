import json
import pytest
from rvw.memory.multihart import images, check


pytestmark = pytest.mark.fast


def test_images(tmp_path):
    elf = tmp_path / 'a file.elf'
    elf.write_bytes(b'\x7fELFexample')
    result = images([f'7={elf}', f'2={elf}'])
    assert [r['hart'] for r in result['harts']] == [2, 7]
    assert len(result['harts'][0]['elf_sha256']) == 64
    with pytest.raises(ValueError):
        images([f'7={elf}', f'7={elf}'])


def fixture(tmp_path, *, reverse=False):
    header = dict(schema='rvw.rvfi/2', xlen=64, isa='rv64ia', core='example', config='two', elf='shared', harts=[0, 1])
    rows = [dict(event='reset', hart=h, epoch=0) for h in [0, 1]]
    actions = [dict(event='external', id='write', action='write', source='dma', address='0x10', data='0x1234', mask='0x3', boundary='ram', serialization='0'),
               dict(event='external', id='read', action='read', source='hart-1', address='0x10', data='0x1234', mask='0x3', boundary='ram', serialization='1', read_from=['write', 'write'])]
    rows += actions[::-1] if reverse else actions
    rows += [dict(event='hart_end', hart=h, epoch=0, status='pass') for h in [0, 1]]
    path = tmp_path / 'trace.jsonl'
    def save():
        path.write_text(json.dumps(header)+'\n'+''.join(json.dumps(r | dict(cycle=i, capture_seq=str(i)))+'\n' for i, r in enumerate(rows)))
    save()
    ref = tmp_path / 'ref.json'
    ref.write_text(json.dumps(dict(schema='rvw.serialized-memory/1', boundary='ram', initial=[dict(address='0x10', bytes='0000')], writes={'write': dict(address='0x10', mask='0x3', data='0x1234')})))
    return path, ref, rows, save


@pytest.mark.parametrize('reverse', [False, True])
def test_serialized_boundary(tmp_path, reverse):
    path, ref, _, _ = fixture(tmp_path, reverse=reverse)
    assert check(path, ref)['status'] == 'consistent'
    assert check(path, ref)['checks'] == 2


@pytest.mark.parametrize('fault,reason', [('data', 'read bytes'), ('read_from', 'read-from')])
def test_read_fault(tmp_path, fault, reason):
    path, ref, rows, save = fixture(tmp_path)
    rows[3][fault] = '0x12' if fault == 'data' else ['initial', 'initial']
    save()
    result = check(path, ref)
    assert result['status'] == 'mismatch'
    assert reason in result['reason']


def test_write_fault_and_incomplete(tmp_path):
    path, ref, rows, save = fixture(tmp_path)
    rows[2]['data'] = '0x5678'
    save()
    assert check(path, ref)['status'] == 'mismatch'
    rows.pop()
    save()
    assert check(path, ref)['status'] == 'inconclusive'


def test_serialization_gap(tmp_path):
    path, ref, rows, save = fixture(tmp_path)
    rows[3]['serialization'] = '2'
    save()
    with pytest.raises(ValueError, match='gap'):
        check(path, ref)


def test_mask_cannot_select_unchecked_lanes(tmp_path):
    path, ref, rows, save = fixture(tmp_path)
    rows[2]['mask'] = '0x100'
    save()
    with pytest.raises(ValueError, match='byte mask'):
        check(path, ref)


def test_missing_independent_write_is_inconclusive(tmp_path):
    path, ref, rows, save = fixture(tmp_path)
    data = json.loads(ref.read_text())
    data['writes'] = {}
    ref.write_text(json.dumps(data))
    assert check(path, ref)['status'] == 'inconclusive'
