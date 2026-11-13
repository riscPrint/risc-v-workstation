from pathlib import Path
from types import SimpleNamespace

import pytest

from rvw.formal.sva_ast import dependency_status,summarize

pytestmark=pytest.mark.fast


def test_summary_keeps_native_operator_and_assertion_kinds():
    tree=dict(kind='Root',members=[dict(kind='ConcurrentAssertion',assertionKind='Assert',
              propertySpec=dict(kind='Binary',op='Intersect',left=dict(kind='Unary',op='FirstMatch')))])
    result=summarize(tree)
    assert result['properties']==[dict(index=0,node_path='$.members[0]',assertion_kind='Assert')]
    assert result['operators']==dict(FirstMatch=1,Intersect=1)
    assert result['node_kinds']['ConcurrentAssertion']==1


def test_non_ast_output_is_not_inspected():
    with pytest.raises(ValueError,match='Root'):
        summarize(dict(kind='Other'))


def test_dependency_evidence_required(tmp_path):
    source=tmp_path/'inputs/a.sv'
    snap=SimpleNamespace(out=tmp_path,sources=[source],files=[dict(frontend='inputs/a.sv')])
    report=tmp_path/'deps.txt'
    assert dependency_status(report,snap)['status']=='inconclusive'
    report.write_text(str(source)+'\n')
    assert dependency_status(report,snap)['status']=='verified'
    report.write_text(str(source)+'\n'+str(tmp_path/'uncaptured.svh')+'\n')
    assert dependency_status(report,snap)['status']=='error'


def test_declared_property_without_active_check_is_no_checks():
    result=summarize(dict(kind='Root',members=[dict(kind='Property',name='p')]))
    assert result['properties']==[]
