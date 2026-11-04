"""Independent contract equations and seeded implementation faults."""
from argparse import Namespace
from pathlib import Path
import json
import shutil

import pytest
from rvw.formal.apps import generate, run

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'SpinalChecks/examples/apps'


def plan():
    return json.loads((FIXTURE / 'apps.json').read_text())


@pytest.mark.parametrize('kind', ['connectivity', 'csr', 'deadlock', 'livelock', 'unr'])
@pytest.mark.parametrize('fault', [False, True])
def test_native_app(tmp_path, kind, fault):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('native Yosys/SBY/Yices required')
    spec = plan()
    spec['properties'] = [p for p in spec['properties'] if p['kind'] == kind]
    rtl = (FIXTURE / 'Contracts.sv').read_text()
    if fault:
        if kind in ('connectivity', 'unr'):
            rtl = rtl.replace('destination = source', 'destination = source ^ 8\'d1')
        elif kind == 'csr':
            rtl = rtl.replace('state <= write_data', 'state <= write_data ^ 8\'d1')
        else:
            rtl = rtl.replace('progress = pending', 'progress = 0')
    (tmp_path / 'Contracts.sv').write_text(rtl)
    path = tmp_path / 'apps.json'
    path.write_text(json.dumps(spec))
    args = Namespace(manifest=str(path), out=str(tmp_path / 'out'), depth=10,
                     engine='smtbmc:yices', timeout=30, mode='bmc', json=False)
    assert run(args) == int(fault)
    result = json.loads((tmp_path / 'out/result.json').read_text())
    assert result['status'] == ('fail' if fault else 'pass')
    child = json.loads((tmp_path / 'out' / spec['properties'][0]['id'] / 'result.json').read_text())
    assert child['assertions'] >= 1
    assert child['proof_kind'] == 'bounded'


def test_refuse_unresolved_forbidden_and_width():
    spec = plan()
    prop = spec['properties'][0]
    with pytest.raises(ValueError, match='unresolved'):
        generate(spec, dict(prop, source='absent'))
    with pytest.raises(ValueError, match='forbidden'):
        generate(spec, dict(prop, relation='forbidden'))
    spec['ports']['destination']['width'] = 9
    with pytest.raises(ValueError, match='same width'):
        generate(spec, prop)


def test_pipeline_gates_startup_and_delays_enable():
    spec = plan()
    text = generate(spec, dict(spec['properties'][0], latency=2, enable='pending'))
    assert 'rvwa_valid0 = 0' in text and 'rvwa_valid1 = 0' in text
    assert 'rvwa_valid1 <= !reset && (rvwa_valid0)' in text
    assert 'destination == rvwa_data1' in text


def test_progress_is_saturating():
    spec = plan()
    text = generate(spec, spec['properties'][2])
    assert 'else if (rvwa_age < 3)' in text


@pytest.mark.parametrize('bad', ['source; assume(0)', '$past(source)', 'missing', 'source()'])
def test_expression_rejects_unsupported(bad):
    spec = plan()
    with pytest.raises(ValueError):
        generate(spec, dict(spec['properties'][-1], target=bad))


def test_wrong_declared_dut_port_map_is_refused(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('native tools required')
    spec = plan()
    spec['properties'] = [spec['properties'][-1]]
    spec['ports']['source']['width'] = 7
    (tmp_path / 'Contracts.sv').write_text((FIXTURE / 'Contracts.sv').read_text())
    path = tmp_path / 'apps.json'
    path.write_text(json.dumps(spec))
    args = Namespace(manifest=str(path), out=str(tmp_path / 'out'), depth=8,
                     engine='smtbmc:yices', timeout=20, mode='bmc', json=False)
    with pytest.raises(SystemExit):
        run(args)
    assert not (tmp_path / 'out/result.json').exists()


@pytest.mark.parametrize('access', ['ro', 'w1c'])
@pytest.mark.parametrize('fault', [False, True])
def test_native_register_access(tmp_path, access, fault):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('native tools required')
    spec = plan()
    prop = dict(spec['properties'][1], access=access, write_mask=15)
    spec['properties'] = [prop]
    rtl = (FIXTURE / 'Contracts.sv').read_text()
    update = 'state' if access == 'ro' else "state & ~(write_data & 8'd15)"
    rtl = rtl.replace('state <= write_data', 'state <= ' + ('write_data' if fault else update))
    (tmp_path / 'Contracts.sv').write_text(rtl)
    path = tmp_path / 'apps.json'
    path.write_text(json.dumps(spec))
    args = Namespace(manifest=str(path), out=str(tmp_path / 'out'), depth=8,
                     engine='smtbmc:yices', timeout=20, mode='bmc', json=False)
    assert run(args) == int(fault)


def test_native_async_register_needs_explicit_event_model(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('native tools required')
    spec = plan()
    spec['properties'] = [spec['properties'][1]]
    rtl = (FIXTURE / 'Contracts.sv').read_text().replace(
        'always @(posedge clk)', 'always @(posedge clk or posedge reset)')
    (tmp_path / 'Contracts.sv').write_text(rtl)
    path = tmp_path / 'apps.json'
    path.write_text(json.dumps(spec))
    args = Namespace(manifest=str(path), out=str(tmp_path / 'refused'), depth=10,
                     engine='smtbmc:yices', timeout=20, mode='bmc', json=False)
    with pytest.raises(SystemExit):
        run(args)
    args.out = str(tmp_path / 'event')
    args.event_model = args.async_reset = True
    assert run(args) == 0


def test_existing_dut_assertion_cannot_be_attributed_to_app(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('native tools required')
    spec = plan()
    spec['properties'] = [spec['properties'][0]]
    rtl = (FIXTURE / 'Contracts.sv').read_text().replace(
        'endmodule', 'always @(posedge clk) assert(source == 0); endmodule')
    (tmp_path / 'Contracts.sv').write_text(rtl)
    path = tmp_path / 'apps.json'
    path.write_text(json.dumps(spec))
    args = Namespace(manifest=str(path), out=str(tmp_path / 'out'), depth=8,
                     engine='smtbmc:yices', timeout=20, mode='bmc', json=False)
    with pytest.raises(SystemExit):
        run(args)
    assert not (tmp_path / 'out/result.json').exists()


@pytest.mark.parametrize('latency,expected', [(0, 'fail'), (1, 'pass')])
def test_native_expression_connectivity_obeys_latency(tmp_path, latency, expected):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('native tools required')
    spec = plan()
    spec['properties'] = [dict(id='registered_progress',kind='connectivity',
                              source_expression='pending != 0',source_width=1,
                              destination='progress',latency=latency)]
    rtl = (FIXTURE / 'Contracts.sv').read_text().replace(
        'output wire progress', 'output reg progress').replace(
        'assign progress = pending;', 'always @(posedge clk) progress <= pending;')
    # Fixture uses a compact output declaration.
    rtl = rtl.replace('output wire progress);', 'output reg progress);')
    (tmp_path / 'Contracts.sv').write_text(rtl)
    path = tmp_path / 'apps.json'
    path.write_text(json.dumps(spec))
    args = Namespace(manifest=str(path), out=str(tmp_path / 'out'), depth=8,
                     engine='smtbmc:yices', timeout=20, mode='bmc', json=False)
    run(args)
    assert json.loads((tmp_path / 'out/result.json').read_text())['status'] == expected
