from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.cov.campaign_artifacts import reference_identity,execution_identity


def reference():
    return {'elf_sha256':'a'*64,'trace_sha256':'b'*64,'tools_rev':'c'*40,'capture':{
        'schema':'rvw.capture/1','problems':[], 'env':{'PATH':'fixture'},
        'files':[{'resolved':'/candidate.elf','sha256':'a'*64},{'resolved':'/trace','sha256':'b'*64},
                 {'resolved':'/libspike.dylib','sha256':'d'*64}],
        'tools':[{'resolved':'/python','sha256':'e'*64,'version':'fixture'}],
        'trees':[{'resolved':'/source','files':[{'resolved':'/source/model.py','sha256':'f'*64},
            {'resolved':'/source/__pycache__/model.pyc','sha256':'0'*64}]}]}}


def test_reference_identity_ignores_payload_and_python_cache_changes():
    a=reference();b=deepcopy(a)
    b.update(elf_sha256='1'*64,trace_sha256='2'*64)
    b['capture']['files'][0].update(resolved='/next.elf',sha256='1'*64)
    b['capture']['files'][1].update(resolved='/next.trace',sha256='2'*64)
    b['capture']['trees'][0]['files'][1]['sha256']='3'*64
    assert reference_identity(a)==reference_identity(b)
    b['capture']['files'][2]['sha256']='4'*64
    assert reference_identity(a)!=reference_identity(b)


def test_execution_identity_binds_c1_and_native_reference():
    run=SimpleNamespace(core='fixture',config='test',tools={'verilator':'fixture'},elf_sha256='a'*64,
        source={'tools_key':'b'*64,'core_rev_full':'c'*40},extra={'rtl_sha256':'d'*64,
            'input_capture':{'inputs_key':'b'*64,'elf_sha256':'a'*64}})
    first=execution_identity(run,{'reproduction':reference()})
    run.extra['rtl_sha256']='e'*64
    assert first!=execution_identity(run,{'reproduction':reference()})
    run.source['identity_complete']=False
    with pytest.raises(ValueError,match='C1 source/native'):
        execution_identity(run,{'reproduction':reference()})


def test_missing_reference_capture_refuses_identity():
    with pytest.raises(ValueError,match='dependency capture'):
        reference_identity({})


def test_adjacent_c1_receipt_varies_without_changing_reference_backend():
    a=reference();b=deepcopy(a)
    a.update(trace='/first/rvfi.jsonl',core_run={'seed':1})
    b.update(trace='/next/rvfi.jsonl',core_run={'seed':2})
    a['capture']['files'].append({'resolved':'/first/result.json','sha256':'1'*64})
    b['capture']['files'].append({'resolved':'/next/result.json','sha256':'2'*64})
    assert reference_identity(a)==reference_identity(b)
