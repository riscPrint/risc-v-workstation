"""Run native Yosys on clean and broken exported RTL."""
import shutil
import pytest
from rvw.lint import yosys

pytestmark = pytest.mark.skipif(not shutil.which('yosys'), reason='needs yosys')


@pytest.mark.parametrize('body,rule', [
    ('assign y = a;', None),
    ('wire missing; assign y = missing;', 'yosys.undriven'),
    ('assign y = ~a; assign y = ~b;', 'yosys.conflicting_drivers'),
    ('wire x; assign x = ~y; assign y = x & a;', 'yosys.combinational_feedback'),
])
def test_native_faults(tmp_path, body, rule):
    source = tmp_path / 'Design.v'
    source.write_text('module Design(input a,b, output y);\n' + body + '\nendmodule\n')
    r = yosys.run([str(source)], 'Design', 20)
    assert r['status'] == 'completed'
    if rule:
        assert rule in {f['rule'] for f in r['findings']}
    else:
        assert not r['findings']
    if rule == 'yosys.undriven':
        f = next(f for f in r['findings'] if f['rule'] == rule)
        assert f['endpoint'] == 'Design.missing'
        assert f['file'] == str(source) and f['line'] == 2
        assert f['elaborated_bits']


def test_unconnected_required_output(tmp_path):
    p = tmp_path / 'Design.v'
    p.write_text('module Design(input a, output y,z); assign z = ~a; endmodule')
    r = yosys.run([str(p)], 'Design', 20)
    assert any(f['endpoint'] == 'Design.y' and f['rule'] == 'yosys.undriven' for f in r['findings'])
