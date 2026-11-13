"""Pinned named-profile requirements and proof/selection evidence."""
import json
from pathlib import Path

import pytest

from rvw.formal.profiles import assess, compare, extract, sha


def fixture(tmp_path, text=None):
    doc = tmp_path / 'profiles.adoc'
    doc.write_text(text or '''=== RVA23U64 Profile
==== RVA23U64 Mandatory Extensions
- *M* Integer multiply.
- *A* Atomics.
==== RVA23U64 Optional Extensions
- *V* Vectors.
=== RVA23S64 Profile
==== RVA23S64 Mandatory Extensions
- *Sstc* Timer.
''')
    isa = tmp_path / 'isa.json'
    isa.write_text(json.dumps(dict(schema='rvw.isa/1',isa='rv64im',extensions={'i':{'version':'2.1'},'m':{'version':'2.0'}},options={})))
    manifest = tmp_path / 'plan.json'
    manifest.write_text(json.dumps(dict(schema='rvw.profile-plan/1',isa_manifest='isa.json',
                                       profiles=['RVA23U64','RVA23S64'],documents=[dict(path='profiles.adoc',sha256=sha(doc.read_bytes()))],
                                       tests={'RVA23U64.m':['present.py','missing.py']},checkers={'RVA23U64.m':['multiply-check']})))
    return doc, isa, manifest


def test_statuses_and_inheritance(tmp_path):
    doc, isa, manifest = fixture(tmp_path)
    report = assess(manifest)
    user, supervisor = (report['profiles'][p] for p in ('RVA23U64','RVA23S64'))
    assert user['implemented'] == ['RVA23U64.m']
    assert user['missing'] == ['RVA23U64.a']
    assert user['not_selected'] == ['RVA23U64.v']
    assert set(supervisor['missing']) == {'RVA23S64.sstc','RVA23S64.a'}
    assert supervisor['implemented'] == ['RVA23S64.m']
    assert report['status'] == 'inconclusive'
    assert report['isa_configuration']['status'] == 'inconclusive'


def test_hash_mismatch(tmp_path):
    doc, _, manifest = fixture(tmp_path)
    doc.write_text(doc.read_text() + 'changed')
    with pytest.raises(ValueError,match='SHA-256'):
        assess(manifest)


def test_proof_binding_and_unbounded_requirement(tmp_path):
    doc, _, manifest = fixture(tmp_path)
    rows = extract(doc, sha(doc.read_bytes()))
    proof = tmp_path / 'proof.json'
    proof.write_text(json.dumps(dict(status='pass',proof_kind='unbounded',assertions=1,reachability={'status':'reachable'},restrictions=['reset then free inputs'])))
    plan = json.loads(manifest.read_text())
    plan['proofs'] = {'RVA23U64.m':dict(result='proof.json',sha256=sha(proof.read_bytes()),obligation_sha256=rows[0]['obligation_sha256'])}
    manifest.write_text(json.dumps(plan))
    assert assess(manifest)['profiles']['RVA23U64']['verified'] == ['RVA23U64.m']
    result = json.loads(proof.read_text()); result['proof_kind'] = 'bounded'
    proof.write_text(json.dumps(result))
    plan['proofs']['RVA23U64.m']['sha256'] = sha(proof.read_bytes())
    manifest.write_text(json.dumps(plan))
    assert assess(manifest)['profiles']['RVA23U64']['verified'] == []


def test_optional_selection_unsupported_and_diff(tmp_path):
    doc, isa, manifest = fixture(tmp_path)
    before = assess(manifest)
    data = json.loads(isa.read_text()); data['isa']='rv64imv'; data['extensions']['v']={'version':'1.0'}
    isa.write_text(json.dumps(data))
    plan = json.loads(manifest.read_text()); plan['unsupported']=['v']
    manifest.write_text(json.dumps(plan))
    after = assess(manifest)
    assert after['profiles']['RVA23U64']['unsupported'] == ['RVA23U64.v']
    difference = compare(before, after)
    assert difference['requires_explicit_adoption']
    assert any(r['id']=='RVA23U64.v' for r in difference['changes'])
    assert 'RVA23U64.m' in difference['missing_tests']


def test_changed_obligation_and_missing_tests(tmp_path):
    doc, _, manifest = fixture(tmp_path)
    (tmp_path / 'present.py').write_text('assert True\n')
    before = assess(manifest)
    doc.write_text(doc.read_text().replace('Integer multiply.', 'Integer multiply and divide.'))
    plan = json.loads(manifest.read_text()); plan['documents'][0]['sha256']=sha(doc.read_bytes())
    manifest.write_text(json.dumps(plan))
    diff = compare(before, assess(manifest))
    row = next(r for r in diff['changes'] if r['id']=='RVA23U64.m')
    assert row['affected_checkers'] == ['multiply-check']
    assert diff['missing_tests']['RVA23U64.m'] == ['missing.py']


def test_cli_and_mcp(tmp_path):
    from rvw.cli import main
    from rvw.formal.mcp_tools import _profiles
    _, _, manifest = fixture(tmp_path)
    class Job:
        def run(self, argv):
            return main(argv[3:])
    assert main(['formal','profiles',str(manifest),'--out',str(tmp_path / 'cli')]) == 3
    assert _profiles(Job(),manifest=str(manifest),out=str(tmp_path / 'mcp'))['status']=='inconclusive'


def test_inherited_mandatory_cannot_be_weakened(tmp_path):
    _, _, manifest = fixture(tmp_path, '''=== RVA23U64 Profile
==== RVA23U64 Mandatory Extensions
- *M* Multiply.
=== RVA23S64 Profile
==== RVA23S64 Optional Extensions
- *M* Multiply.
''')
    profile = assess(manifest)['profiles']['RVA23S64']
    assert profile['obligations'][0]['requirement'] == 'mandatory'
    assert profile['obligations'][0]['active']
