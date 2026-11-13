import json
import pytest
from lint_builder import Builder
from rvw.formal.bus_bindings import generate
from test_typed_bus_checks import fields


def inputs(tmp_path):
    db=Builder(tmp_path/'design.db')
    db.domain(1,reset='reset',kind='SYNC')
    db.sig('clk',direction='in');db.sig('reset',direction='in')
    db.c.execute("INSERT INTO bundles(id,component_id,path,class_name) VALUES(1,1,'io.bus','Bus')")
    names=[]
    for key,row in fields('tilelink').items():
        name='io_bus_'+row[0];names.append(name)
        db.sig(name,width=row[3],domain=1)
        db.c.execute('UPDATE signals SET spinal_path=? WHERE name=?',('io.bus.'+key,name))
    db.done()
    info=dict(schema='rvw.checks/1',toplevel='Top',buses=[dict(path='',object='io_bus',
              class_name='spinal.lib.bus.tilelink.Bus',signals=names,options=dict(size_max=4,with_bce=0))])
    return info


def test_exact_elaborated_signal_inventory_binds_ambiguous_bus(tmp_path):
    info=inputs(tmp_path);report=tmp_path/'types.json';report.write_text(json.dumps(info))
    result=generate(tmp_path/'design.db',tmp_path/'out',type_report=report)
    row=result['buses'][0]
    assert row['status']=='generated' and row['kind']=='tilelink'
    assert row['recorded_class']=='Bus'
    assert row['options']['size_max']==4
    assert row['type_source']==str(report)


@pytest.mark.parametrize('fault',['missing_signal','wrong_path','duplicate','wrong_class'])
def test_nonmatching_or_ambiguous_inventory_stays_unsupported(tmp_path,fault):
    info=inputs(tmp_path)
    if fault=='missing_signal':info['buses'][0]['signals'].pop()
    if fault=='wrong_path':info['buses'][0]['path']='child'
    if fault=='duplicate':info['buses']*=2
    if fault=='wrong_class':info['buses'][0]['class_name']='some.other.Bus'
    report=tmp_path/'types.json';report.write_text(json.dumps(info))
    result=generate(tmp_path/'design.db',tmp_path/'out',type_report=report)
    assert result['status']=='no_checks'
    assert result['buses'][0]['status']=='unsupported'


def test_wrong_top_is_an_error(tmp_path):
    info=inputs(tmp_path);info['toplevel']='Other'
    report=tmp_path/'types.json';report.write_text(json.dumps(info))
    with pytest.raises(ValueError,match='top differs'):
        generate(tmp_path/'design.db',tmp_path/'out',type_report=report)
