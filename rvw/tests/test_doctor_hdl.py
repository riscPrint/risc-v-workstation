"""Spinal build tools are not HDL project prerequisites."""
import json
from types import SimpleNamespace
import pytest
from rvw.doctor import check
from rvw.init.hdl import scaffold_hdl

pytestmark=pytest.mark.fast


def test_hdl_diagnostics_do_not_require_jvm_tools(tmp_path,monkeypatch):
    (tmp_path/'top.v').write_text('module top; endmodule')
    scaffold_hdl(tmp_path,hdl='sv',top='top',isa='rv32i',name='plain')
    def run(command,**kw):
        text=' '.join(map(str,command))
        if '--check' in command:
            return SimpleNamespace(returncode=1,stdout='MISSING JDK: absent\nMISSING javac: absent\nMISSING sbt: absent\nPRESENT Verilator: 5.052\nPRESENT make: 4.0\nPRESENT C++: 21.0\n',stderr='')
        if 'info' in command:
            stdout=json.dumps(dict(schema='rvw.adapter/1',core='plain',configs=['default'],default_config='default',xlen=32,isa=dict(default='rv32i')))
        else: stdout='1'*40 if 'rev-parse' in command else ''
        return SimpleNamespace(returncode=0,stdout=stdout,stderr='')
    monkeypatch.setattr(check,'run_group',run)
    report=check.diagnose(project=tmp_path,features='sim')
    assert next(c for c in report['checks'] if c['name']=='native')['status']=='ready'
    rows={r['tool']:r for r in report['native']}
    assert all(rows[name]['status']=='not_applicable' for name in ('JDK','javac','sbt'))
    assert rows['Verilator']['status']=='ready'


def test_spinal_still_requires_jvm_tools():
    rows=[dict(tool='sbt',status='error')]
    assert check.hdl_native_records(rows,'spinal')==rows
    assert check.hdl_native_records(rows,None)==rows
