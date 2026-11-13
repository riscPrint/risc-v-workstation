import json
import shutil
import subprocess
from argparse import Namespace

import pytest

from rvw.formal.property_library import from_channels, render, run
from rvw.formal.temporal import Unsupported, lower


SPECS = [
    dict(id='hold', kind='handshake', valid='v', ready='r', payload='d', width=8),
    dict(id='count', kind='fifo', count='n', push='push', pop='pop', depth=4, width=3),
    dict(id='grant', kind='one-hot', bits='g', allow_zero=False),
    dict(id='fair', kind='arbiter-fairness', request='req', grant='ack', bound=3),
    dict(id='response', kind='request-response', request='req', response='ack', bound=3),
    dict(id='flow', kind='flow', valid='v', payload='d', max_value=10),
]


@pytest.mark.parametrize('spec', SPECS)
def test_lower_all_intents(spec):
    source = render(spec)
    lowered, rows = lower('module m;\n' + source + '\nendmodule')
    assert rows
    assert all(row['kind'] == 'assert' for row in rows)


def test_typed_channels():
    report = {'schema': 'rvw.checks/1', 'channels': [
        dict(kind='Stream', path='Top', object='io_tx', valid='Top.io_tx_valid',
             ready='Top.io_tx_ready', payload=['Top.io_tx_payload'])]}
    bindings = {'Top.io_tx': dict(id='tx', clock='other_clk', reset='rst', width=8,
                                ports={'Top.io_tx_valid': 'v', 'Top.io_tx_ready': 'r', 'Top.io_tx_payload': 'd'})}
    intents = from_channels(report, bindings)
    assert intents[0]['kind'] == 'handshake'
    assert '@(posedge other_clk)' in render(intents[0])
    with pytest.raises(Unsupported, match='channel_clock_binding'):
        from_channels(report, {})
    report['channels'][0].update(kind='Flow', ready=None)
    bindings['Top.io_tx']['max_value'] = 20
    assert 'hold' not in render(from_channels(report, bindings)[0])


def test_generate(tmp_path):
    spec = tmp_path / 'spec.json'
    spec.write_text(json.dumps({'properties': SPECS}))
    out = tmp_path / 'intents.sv'
    assert run(Namespace(spec=str(spec), channels=None, out=str(out))) == 0
    assert 'count_count_step' in out.read_text()


@pytest.mark.parametrize('index', range(len(SPECS)))
@pytest.mark.parametrize('mutant', [False, True])
def test_native_intent(tmp_path, index, mutant):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    designs = [
        'wire v=1, r=0; reg [7:0] d=0; always @(posedge clk) d<=' + ('d+1;' if mutant else 'd;'),
        'wire push=0, pop=0; wire [2:0] n=' + ('7;' if mutant else '0;'),
        'wire [1:0] g=' + ('3;' if mutant else '1;'),
        'wire req=1, ack=' + ('0;' if mutant else '1;'),
        'wire req=1, ack=' + ('0;' if mutant else '1;'),
        'wire v=1; wire [7:0] d=' + ('11;' if mutant else '10;'),
    ]
    source, _ = lower('module m(input clk);\n' + designs[index] + render(SPECS[index]) + '\nendmodule')
    (tmp_path / 'm.sv').write_text(source)
    (tmp_path / 'job.sby').write_text('''[options]
mode bmc
depth 12
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    result = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('FAIL' if mutant else 'PASS'), result.stdout
