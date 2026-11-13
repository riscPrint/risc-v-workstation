import json
import pytest
from rvw.sec.suite import collect
from rvw.results.schema import validate_results
pytestmark=pytest.mark.fast


def test_incomplete_report_does_not_pass(tmp_path):
    file=tmp_path/'sample.json'
    file.write_text(json.dumps(dict(schema='rvw.sec/1',technique='ift',status='no_leak_observed',complete=False)))
    r=collect([file],tmp_path/'suite')
    assert r['status']=='inconclusive'
    assert json.loads((tmp_path/'suite/results.json').read_text())['tests'][0]['status']=='error'


def test_aggregate_retains_failure_and_missing(tmp_path):
    file=tmp_path/'sample.json'
    file.write_text(json.dumps(dict(schema='rvw.sec/1',technique='latency',status='violation',complete=True,
                                    findings=[{'cycle':2}])))
    r=collect([file,tmp_path/'missing'],tmp_path/'suite')
    assert r['status']=='violation' and not r['complete']
    data=json.loads((tmp_path/'suite/results.json').read_text())
    assert [e['status'] for e in data['tests']]==['fail','error']
    assert not validate_results(data)



def test_partial_violation_remains_incomplete(tmp_path):
    f=tmp_path/'report.json'
    f.write_text(json.dumps(dict(schema='rvw.sec/1',technique='ift',status='violation',complete=False,findings=[{}])))
    r=collect([f],tmp_path/'out')
    assert r['status']=='violation' and r['complete'] is False


def test_generated_suite_cannot_earn_execution_result(tmp_path):
    f=tmp_path/'generated.json';f.write_text(json.dumps(dict(schema='rvw.sec-gadgets/1',status='generated')))
    assert collect([f],tmp_path/'out')['status']=='inconclusive'


def test_cli_and_mcp_surface():
    from rvw.cli import build_parser
    from rvw.mcp.registry import discover
    tools,problems=discover({'sec'})
    assert not problems
    assert {t.name for t in tools}=={'sec_ift','sec_contract','sec_gadgets','sec_latency','sec_isolation','sec_fault','sec_suite','sec_ift_core','sec_spec_suite','sec_campaign','sec_model_check'}
    args=build_parser().parse_args(['sec','suite','--report','run/report.json','--out','summary'])
    assert args.sec_command=='suite'
