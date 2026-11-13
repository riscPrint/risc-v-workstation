import json
from hashlib import sha256
import pytest
from rvw.arch.warmup import warmup_bias
from test_ooo import trace


def fixture(tmp_path):
    elf = tmp_path/'elf'
    elf.write_bytes(b'elf')
    t = tmp_path/'trace'
    trace(t)
    for name, start, cycles in [('base', 2, 10), ('cold', 0, 15), ('warm', 1, 11)]:
        (tmp_path/name).write_text(json.dumps(dict(schema='rvw.run/1', status='pass',
            core='test', config='tiny', elf='test.elf', elf_sha256=sha256(b'elf').hexdigest(),
            instret=4, seed=1, mem_latency=0,
            metrics=dict(roi_start_order=start, roi_instret=2, roi_cycles=cycles))))
    data = dict(schema='rvw.arch-warmup-plan/1', elf='elf', start=2, length=2, target_percent=20,
        baseline=dict(c1='base', trace='trace'), samples=[dict(c1='cold', trace='trace', warmup=0),
                                                         dict(c1='warm', trace='trace', warmup=1)])
    p = tmp_path/'plan'
    p.write_text(json.dumps(data))
    return p, data


def test_fixed_roi_bias_and_exclusive_output(tmp_path):
    p, _ = fixture(tmp_path)
    out = tmp_path/'out'
    r = warmup_bias(p, out)
    assert r['samples'][0]['signed_cpi_bias_percent'] == 50
    assert not r['samples'][0]['observed_within_budget']
    assert r['samples'][1]['signed_cpi_bias_percent'] == pytest.approx(10)
    assert r['samples'][1]['capture'] == 1
    assert r['samples'][1]['observed_within_budget']
    assert r['accuracy_status'] == 'inconclusive'
    with pytest.raises(FileExistsError):
        warmup_bias(p, out)


@pytest.mark.parametrize('change', ['seed', 'roi', 'suffix', 'missing', 'duplicate', 'target'])
def test_reject_invalid_observations(tmp_path, change):
    p, data = fixture(tmp_path)
    if change == 'duplicate':
        data['samples'][1]['warmup'] = 0
    elif change == 'target':
        data['target_percent'] = -1
    elif change == 'suffix':
        t = tmp_path/'badtrace'
        trace(t, insn='0x93')
        data['samples'][0]['trace'] = t.name
    elif change == 'missing':
        (tmp_path/'base').unlink()
    else:
        path = tmp_path/'cold'
        row = json.loads(path.read_text())
        if change == 'seed': row['seed'] = 2
        if change == 'roi': row['metrics']['roi_start_order'] = 1
        path.write_text(json.dumps(row))
    p.write_text(json.dumps(data))
    with pytest.raises((ValueError, OSError)):
        warmup_bias(p, tmp_path/'out')
