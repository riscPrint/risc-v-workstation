from pathlib import Path
from hashlib import sha256
import copy
import json
import pytest
from rvw.cov.exchange import export_ucis,import_ucis,normalized,merge_exchanges,dat_bytes
from rvw.cov.code import read_counts


def functional():
    return {'schema':'rvw.functional-coverage/1','config_sha256':'a'*64,'config':{'groups':[]},
            'groups':{'operand':{'fields':['value'],'hits':[{'bin':['zero'],'count':3}],'holes':[['one']]}}}


def code():
    key='\x01f\x02a.v\x01l\x0212\x01t\x02toggle'
    return {'schema':'rvw.coverage/1','point_universe':'a'*64,'source_root':'.','source_revision':'a'*40,
            'sources':{'a.v':{'sha256':'b'*64,'path':'a.v'}},'points':[{'id':sha256(key.encode()).hexdigest(),
             'key':key,'fields':{'f':'a.v','l':'12','t':'toggle'},'count':3,
             'exclusion':{'reason':'transported, unverified'},'scala':{'file':'a.scala','line':4}}]}


@pytest.mark.parametrize('report',[functional(),code(),{'schema':'rvw.assertion-counters/1','design_sha256':'c'*64,
    'properties':[{'id':'p','source':{'file':'p.sv','line':4},'counts':{'pass':2,'fail':0,'vacuous':1}}]}])
def test_ucis_counter_profile_round_trip_preserves_semantics(report):
    xml=export_ucis(report)
    parsed=import_ucis(xml)
    assert parsed==normalized(report)
    assert parsed['proof_exclusions_verified'] is False
    assert b'xmlns="UCIS"' in xml


def test_unseen_denominator_and_incompatible_merge():
    a=normalized(functional());b=normalized(functional())
    merged=merge_exchanges([a,b])
    assert len(merged['rows'])==2
    assert sum(r['count'] for r in merged['rows'])==6
    b['context']['config_sha256']='changed'
    with pytest.raises(ValueError,match='incompatible'):
        merge_exchanges([a,b])
    b=normalized(code());a=normalized(code());b['rows'][0]['metadata']['exclusion']={'reason':'changed'}
    with pytest.raises(ValueError,match='incompatible'):
        merge_exchanges([a,b])


def test_unsupported_xml_and_duplicate_ids_refuse():
    xml=export_ucis(functional())
    with pytest.raises(ValueError,match='unsupported'):
        import_ucis(xml.replace(b'rvw-counter-profile/1',b'other-profile'))
    with pytest.raises(ValueError,match='entities'):
        import_ucis(b'<!DOCTYPE test>'+xml)
    report=normalized(functional());report['rows'].append(report['rows'][0])
    with pytest.raises(ValueError,match='duplicate'):
        export_ucis(report)


def test_native_dat_keeps_exact_counter_keys(tmp_path):
    report=code();path=tmp_path/'out.dat';path.write_bytes(dat_bytes(report))
    assert read_counts(path)=={report['points'][0]['id']:3}
    report['points'][0]['key']='changed'
    with pytest.raises(ValueError,match='native coverage point'):
        dat_bytes(report)


def test_cli_mcp_export_parity_and_sidecars(tmp_path):
    import subprocess,sys
    from rvw.cov.exchange_cli import execute_json
    source=tmp_path/'report.json';source.write_text(json.dumps(functional()))
    cli_path=tmp_path/'cli.xml';api_path=tmp_path/'api.xml'
    ran=subprocess.run([sys.executable,'-m','rvw','cov','exchange',str(source),'--destination',str(cli_path),'--json'],capture_output=True,text=True)
    assert ran.returncode==0,ran.stderr
    api=execute_json(database=source,destination=api_path)
    assert json.loads(ran.stdout)['sha256']==api['sha256']
    assert Path(str(cli_path)+'.rvw.json').is_file()


def test_malformed_xml_is_a_reported_input_error():
    with pytest.raises(ValueError,match='invalid UCIS XML'):
        import_ucis(b'<UCIS')


def test_assertion_peak_and_active_snapshot_merge_semantics():
    def report(peak,active):
        return {'schema':'rvw.assertion-counters/1','design_sha256':'a'*64,
                'properties':[{'id':'p','counts':{'peak_active':peak,'active':active,'pass':2}}]}
    merged=merge_exchanges([report(3,1),report(5,1)])
    counts={row['kind']:row['count'] for row in merged['rows']}
    assert counts['assertion:peak_active']==5
    assert counts['assertion:active']==1 and counts['assertion:pass']==4
    with pytest.raises(ValueError,match='active assertion snapshots'):
        merge_exchanges([report(3,1),report(5,2)])
