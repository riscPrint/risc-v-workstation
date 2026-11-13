import pytest
from rvw.formal import runtime
from rvw.formal.isa import bounded_rows, table

pytestmark = pytest.mark.fast


def test_timeout_does_not_claim_capacity(monkeypatch):
    monkeypatch.setattr(runtime.os, 'getloadavg', lambda: (61., 50., 40.))
    row = runtime.timeout_details(1800.2, 1800, [60., 51., 42.], engine='abc:pdr')
    assert row['capacity_classification'] == 'unresolved'
    assert row['load_average_end'] == [61., 50., 40.]
    assert '--timeout 3600' in row['next_setting']
    assert 'at most two engines' in row['next_setting']


def test_missing_load_is_explicit(monkeypatch):
    def missing():
        raise OSError('not available')
    monkeypatch.setattr(runtime.os, 'getloadavg', missing)
    assert runtime.load_average() is None
    assert '--timeout 1800' in runtime.timeout_details(20, 20, None)['next_setting']


def test_low_load_timeout_still_needs_evidence():
    row = runtime.timeout_details(1801, 1800, [1.,2.,3.])
    assert row['capacity_classification'] == 'unresolved'
    assert 'one-minute load' not in row['next_setting']


def test_conditional_summary_keeps_engine_timing():
    from rvw.formal.instruction_attempts import summarize
    native = dict(engine='abc:pdr', status='timeout',
                  **runtime.timeout_details(1800.1,1800,[80.,90.,100.]))
    row = summarize(dict(rtlil_retry=dict(rows=[native])))
    assert row['engines'][0]['wall_s'] == 1800.1
    assert row['engines'][0]['capacity_classification'] == 'unresolved'


def test_activation_timeout_keeps_load(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    from rvw.formal import isa_activation
    work=tmp_path/'riscv-formal/cores/project/checks'
    work.mkdir(parents=True)
    (work/'insn_add_ch0.sby').write_text('[options]\nmode bmc\n[engines]\nsmtbmc yices\n[script]\n')
    (tmp_path/'results.json').write_text(json.dumps(dict(tests=[dict(id='insn_add_ch0',status='pass')])))
    monkeypatch.setattr(isa_activation,'run_group',lambda *a,**kw: SimpleNamespace(returncode=-15,timed_out=True))
    result=isa_activation.run(dict(solver='yices'),tmp_path,20)
    activation=result['tests'][0]['instruction_activation']
    assert activation['status']=='timeout' and activation['timeout_s']==20
    assert 'load_average_start' in activation and '--timeout 1800' in activation['next_setting']


def test_machine_timeout_keeps_per_task_load(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from rvw.formal import machine_checks
    (tmp_path/'x0').mkdir()
    monkeypatch.setattr(machine_checks,'generate',lambda *a:dict(rows=[dict(check='x0',status='generated')]))
    monkeypatch.setattr(machine_checks,'run_group',lambda *a,**kw:SimpleNamespace(returncode=-15,timed_out=True))
    result=machine_checks.run({},tmp_path,tmp_path,20)
    row=result['rows'][0]
    assert row['status']=='inconclusive'
    assert [r['task'] for r in row['native_attempts']]==['check','cover']
    assert all(r['status']=='timeout' and 'load_average_start' in r for r in row['native_attempts'])


def test_isa_table_keeps_timeout_measurements():
    details = runtime.timeout_details(150.2, 150, [70., 60., 50.])
    row = dict(id='insn_add_ch0', status='timeout', **details)
    rows = bounded_rows(dict(tests=[row], bounded_depth=20))
    assert rows[0]['wall_s'] == 150.2
    text = table(dict(rows=rows))
    assert 'ran 150.2 s' in text and 'limit 150 s' in text and '70.0' in text
    assert '--timeout 1800' in text


def test_bounded_runner_records_host_pressure(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from rvw.formal import riscv
    monkeypatch.setattr(riscv, 'prepare', lambda cfg, out: (tmp_path, {}))
    (tmp_path/'checks').mkdir()
    for name in ('insn_add_ch0', 'cover'):
        (tmp_path/'checks'/f'{name}.sby').write_text('[engines]\nsmtbmc yices\n')
    monkeypatch.setattr(runtime.os, 'getloadavg', lambda: (25., 24., 23.))
    monkeypatch.setattr(riscv, 'invoke', lambda *a, **kw: SimpleNamespace(returncode=0, timed_out=True))
    cfg = dict(checks=['insn_add_ch0','cover'], depth=20, solver='yices', isa='rv32i')
    riscv.run(cfg, tmp_path, 1800, 'test')
    import json
    result = json.loads((tmp_path/'results.json').read_text())
    assert result['tests'][0]['load_average_start'] == [25.,24.,23.]
    assert result['tests'][0]['timeout_s'] == 1800
    assert result['tests'][0]['capacity_classification'] == 'unresolved'
    assert result['tests'][0]['timeout_phase'] == 'generation'


@pytest.mark.parametrize('prepare_timeout', [False, True])
def test_portfolio_timeout_records_host_pressure(tmp_path, monkeypatch, prepare_timeout):
    import hashlib
    from types import SimpleNamespace
    from rvw.formal import portfolio
    monkeypatch.setattr(portfolio.shutil, 'which', lambda _: __file__)
    monkeypatch.setattr(runtime.os, 'getloadavg', lambda: (21., 20., 19.))
    def native(command, **kwargs):
        preparing = command[0] == 'yosys'
        if preparing and not prepare_timeout:
            (kwargs['cwd']/'design.json').write_text('{"modules":{"top":{"cells":{"a":{"type":"$assert"}}}}}')
        return SimpleNamespace(stdout='', stderr='', returncode=0,
                               timed_out=prepare_timeout if preparing else True)
    monkeypatch.setattr(portfolio, 'run_group', native)
    source = tmp_path/'model.sv'
    source.write_text('module top; always @* assert(0); endmodule')
    plan = dict(top='top', engines=['abc:pdr'], sources=[dict(path=source.name,
                sha256=hashlib.sha256(source.read_bytes()).hexdigest())])
    result = portfolio.race(plan, tmp_path, tmp_path/'out', timeout=1800)
    row = result if prepare_timeout else result['rows'][0]
    assert row['load_average_start'] == [21.,20.,19.]
    assert row['timeout_s'] == 1800 and row['wall_s'] >= 0
    assert row['capacity_classification'] == 'unresolved'
    assert result['status'] == 'inconclusive'
