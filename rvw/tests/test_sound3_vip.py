import importlib
import pytest
from rvw.vip.apb import ProtocolError

pytestmark = pytest.mark.fast

@pytest.mark.parametrize('name', ['axi', 'axis', 'tilelink', 'wishbone', 'apb', 'ahb', 'spi', 'i2c', 'jtag', 'dram'])
def test_idle_monitor_is_no_checks(name):
    monitor = importlib.import_module('rvw.vip.'+name).Monitor()
    with pytest.raises(ProtocolError) as error:
        monitor.finish()
    assert getattr(error.value, 'status', None) == 'no_checks'
    assert monitor.finish(idle_reason='unused in this scenario')['status'] == 'idle'


def test_intentional_idle_does_not_hide_unfinished_packet():
    from rvw.vip.axis import Monitor
    monitor = Monitor()
    monitor.partial[(0, 0)] = [1]
    with pytest.raises(ProtocolError, match='UNTERMINATED'):
        monitor.finish(idle_reason='unused')


def test_complete_response_is_checked():
    from rvw.vip.axi import Monitor
    monitor = Monitor()
    monitor.completed = 1
    assert monitor.finish() == {'status': 'checked', 'transactions': 1}

@pytest.mark.parametrize('name', ['axi','axis','tilelink','apb','ahb','wishbone','spi','i2c','jtag','uart','gpio','sram','interrupt','clock_reset','coherent','stress'])
def test_uvm_monitors_have_empty_traffic_guard(name):
    from pathlib import Path
    source=(Path(__file__).resolve().parents[2]/'Uvm/vip'/name/(name+'_pkg.sv')).read_text()
    monitor=source.split('class monitor',1)[1].split('endclass',1)[0]
    assert '`uvm_fatal("NO_CHECKS"' in monitor
    assert 'idle_reason.len()==0' in monitor
