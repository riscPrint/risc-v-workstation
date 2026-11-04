"""Independent queue oracle checks selected CDC RTL, including seeded faults."""
import json
from pathlib import Path
import shutil
import pytest
from rvw.cli import main
from rvw.lint import protocol

REFERENCES = Path(__file__).resolve().parents[2] / 'SpinalChecks' / 'examples' / 'cdc'


def plan(kind):
    return dict(schema='rvw.cdc-protocol/1', kind=kind,
                top={'handshake':'cdc_handshake', 'async_fifo':'cdc_fifo', 'reset_release':'cdc_reset'}[kind],
                verilog=['sampling.sv', {'handshake':'handshake', 'async_fifo':'fifo', 'reset_release':'reset'}[kind] + '.sv'])


@pytest.mark.parametrize('kind', ['handshake', 'async_fifo', 'reset_release'])
@pytest.mark.parametrize('fault', [False, True])
@pytest.mark.skipif(not all(shutil.which(t) for t in ['yosys','sby','yices-smt2']), reason='needs native formal tools')
def test_native_protocol(tmp_path, kind, fault):
    cfg = plan(kind)
    for name in cfg['verilog']:
        text = (REFERENCES / name).read_text()
        (tmp_path / name).write_text(('`define CDC_FAULT\n' if fault and name != 'sampling.sv' else '') + text)
    path = tmp_path / 'spec.json'; path.write_text(json.dumps(cfg))
    out = tmp_path / 'out'
    rc = main(['lint','--protocol',str(path),'--out',str(out), '--mode','prove',
               '--engine','abc:pdr','--timeout','60','--json'])
    r = json.loads((out / 'result.json').read_text())
    assert r['status'] == ('fail' if fault else 'pass')
    assert rc == int(fault)
    assert r['proof_kind'] == 'unbounded'
    assert r['activation'] == 'not_measured'


def test_monitor_is_independent_queue():
    text, ports = protocol.generate(plan('async_fifo'))
    assert 'data_out == expected[head]' in text
    assert 'count < 4' in text and 'count > 0' in text
    assert ports['data_out'] == dict(direction='output', width=8)
    assert ports['forward_choice']['direction'] == 'input'


def test_unknown_protocol():
    with pytest.raises(ValueError, match='kind'):
        protocol.generate({'kind':'unknown'})


@pytest.mark.parametrize('kind', ['handshake', 'async_fifo', 'reset_release'])
@pytest.mark.parametrize('fault', [False, True])
@pytest.mark.skipif(not all(shutil.which(t) for t in ['iverilog','vvp']), reason='needs Icarus')
def test_perturbed_native_simulation(tmp_path, kind, fault):
    cfg = plan(kind)
    for name in cfg['verilog']:
        (tmp_path / name).write_text(('`define CDC_FAULT\n' if fault and name != 'sampling.sv' else '') + (REFERENCES / name).read_text())
    path = tmp_path / 'spec.json'; path.write_text(json.dumps(cfg))
    out = tmp_path / 'out'
    rc = main(['lint','--protocol',str(path),'--out',str(out),'--simulate','1000','--seed','42'])
    r = json.loads((out / 'result.json').read_text())
    assert r['status'] == ('fail' if fault else 'pass')
    assert rc == int(fault)
    assert r['schema'] == 'rvw.cdc-simulation/1'
