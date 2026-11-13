from pathlib import Path
import shutil
import subprocess

import pytest

from rvw.formal.channel_bindings import bind_database
from rvw.formal.property_library import from_channels, render
from rvw.formal.temporal import Unsupported, lower
from rvw.query.db import DesignDB


REPORT = {'schema': 'rvw.checks/1', 'channels': [dict(
    kind='Stream', path='fifo', object='io_push', valid='fifo.io_push_valid', ready='fifo.io_push_ready',
    payload=['fifo.io_push_payload_0', 'fifo.io_push_payload_1'])]}


def test_database_clock_binding(cluster_db):
    db = DesignDB(cluster_db)
    try:
        with pytest.raises(Unsupported, match='channel_clock_binding'):
            bind_database(REPORT, {}, db)
        bindings = bind_database(REPORT, {'fifo.io_push': dict(domain_signal='fifo.logic_ptr_push')}, db)
        spec = from_channels(REPORT, bindings)[0]
        assert spec['clock'] == 'clk' and spec['reset'] == 'reset'
        assert spec['payloads'] == [dict(signal=f'io_push_payload_{i}', width=16, max_value=None) for i in (0,1)]
        rtl, props = lower('module m;\n' + render(spec) + '\nendmodule')
        assert len(props) == 3
        assert 'stable_0' in render(spec) and 'stable_1' in render(spec)
    finally:
        db.close()


def test_composite_flow():
    source = render(dict(kind='flow', id='rx', valid='v', payloads=[
        dict(signal='data', max_value=20), dict(signal='tag', max_value=3)]))
    assert 'data <= 20' in source and 'tag <= 3' in source
    assert 'hold' not in source
    with pytest.raises(ValueError, match='each field'):
        render(dict(kind='flow', id='rx', valid='v', payloads=[dict(signal='data')]))


def test_low_reset():
    source = render(dict(kind='handshake', id='tx', valid='v', ready='r', reset='rst_n', reset_active='low',
                         payloads=[dict(signal='data', width=8), dict(signal='tag', width=2)]))
    assert 'disable iff (!rst_n)' in source


@pytest.mark.parametrize('field', ['none', 'data', 'tag'])
def test_native_composite_payload(tmp_path, field):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    spec = dict(kind='handshake', id='tx', valid='v', ready='r',
                payloads=[dict(signal='data', width=8), dict(signal='tag', width=2)])
    design = ('module m(input clk); wire v=1,r=0; reg [7:0] data=0; reg [1:0] tag=0; '
              + ('always @(posedge clk) data<=data+1; ' if field == 'data' else '')
              + ('always @(posedge clk) tag<=tag+1; ' if field == 'tag' else ''))
    rtl, _ = lower(design + render(spec) + 'endmodule')
    (tmp_path / 'm.sv').write_text(rtl)
    (tmp_path / 'job.sby').write_text('''[options]
mode bmc
depth 8
[engines]
smtbmc yices
[script]
read -formal m.sv
prep -top m
[files]
m.sv
''')
    run = subprocess.run(['nice', '-n', '10', 'sby', '-f', 'job.sby'], cwd=tmp_path,
                         capture_output=True, text=True, timeout=30)
    assert (tmp_path / 'job/status').read_text().split()[0] == ('PASS' if field == 'none' else 'FAIL'), run.stdout
