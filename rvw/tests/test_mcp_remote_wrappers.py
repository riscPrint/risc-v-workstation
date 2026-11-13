import json
import shutil
from pathlib import Path

import pytest
import rvw

pytest.importorskip('mcp')
from lint_builder import Builder
from rvw.mcp.registry import discover
from rvw.mcp.remote import ClientRegistry, remote_tool

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('argument', ['db', 'db_path'])
def test_remote_wrapped_alias_reaches_the_worker(tmp_path, argument):
    builder = Builder(tmp_path / 'design.db')
    builder.domain(1, clock='clk')
    builder.sig('clk', direction='in', role='clock')
    builder.reg('q', 1)
    ports = {}
    for pin, width in [('PADDR', 32), ('PSEL', 1), ('PENABLE', 1), ('PWRITE', 1),
                       ('PWDATA', 32), ('PRDATA', 32), ('PREADY', 1)]:
        builder.sig(pin, width=width, direction='in')
        ports[pin] = pin
    builder.sig('RAM_ADDR', width=12, direction='in')
    database = builder.done()
    bindings = tmp_path / 'bindings.json'
    bindings.write_text(json.dumps(dict(interrupts={}, bus_ports={
        'core.bus': ports, 'ram.io.bus': {**ports, 'PADDR': 'RAM_ADDR'}})))
    source = tmp_path / 'soc.json'
    shutil.copyfile(Path(rvw.__file__).resolve().parents[3] / 'SpinalSoc/examples/soc.json', source)
    spec = next(tool for tool in discover({'soc'})[0] if tool.name == 'soc_audit')
    registry = ClientRegistry([remote_tool(spec)], project=str(tmp_path))
    try:
        output = tmp_path / 'audit.json'
        started = registry.call('soc_audit', dict(source=str(source), bindings=str(bindings),
                                                out=str(output), **{argument: str(database)}))
        state = registry.call('job_status', dict(job_id=started['job_id'], wait_s=20))
        assert state['status'] == 'done', state
        assert state['result']['status'] == 'inconclusive'
        assert len(state['result']['bus_ports']) == 2
        assert output.is_file()
    finally:
        registry.jobs.shutdown()
