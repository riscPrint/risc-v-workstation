"""Preserve mandatory bases, nested Sha definitions and conditional PMM clauses."""
from pathlib import Path
from rvw.formal.profile_clauses import additional,expand_sha,active,declared


def test_base_nested_and_conditional():
    text='''=== RVA23U64 Profile
==== RVA23U64 Mandatory Base

RV64I is mandatory and little-endian. ECALL requests a trap.

=== RVA23S64 Profile
==== RVA23S64 Mandatory Extensions
- *Sha* Augmented hypervisor.

*Sha* comprises the following extensions:

** *H* Hypervisor.
** *Ssstateen* State-enable registers must be provided.
=== RVB23S64 Profile
==== RVB23S64 Optional Extensions
- If the hypervisor extension is implemented and pointer masking
  (Ssnpm) is supported then henvcfg.PMM must support PMLEN=0 and 7.
'''
    rows=additional(Path('profiles.adoc'),'hash',text.splitlines())
    assert [row['id'] for row in rows]==['RVA23U64.base','RVA23S64.h','RVA23S64.ssstateen','RVB23S64.hypervisor_pointer_mask']
    condition=rows[-1]
    assert not active(condition,{'ssnpm'})
    assert active(condition,{'h','ssnpm'})
    assert active(condition,{'sha','ssnpm'})
    base=rows[0]
    assert not declared(base,{'i'},64,{})
    assert declared(base,{'i'},64,{'declarations':{base['id']:True}})
    assert not declared(base,{'i'},32,{'declarations':{base['id']:True}})
    parent=dict(profile='RVB23S64',extension='sha')
    expanded=expand_sha(rows+[parent],{'sha'})
    inherited=next(row for row in expanded if row.get('id')=='RVB23S64.h')
    assert inherited['when_any']==[['sha']]
    assert inherited['source']==rows[1]['source']


def test_scope_notes_stay_with_obligation():
    from rvw.formal.profile_clauses import bullet_end
    lines=['- *Ssstrict* Raise a trap.', '', 'NOTE: Custom encodings are excluded.', '',
           'NOTE: The guest VM need not implement this profile.', '', '- *Other* Next.']
    assert bullet_end(lines,0)==5


def test_missing_selected_sha_definition_is_refused():
    import pytest
    with pytest.raises(ValueError,match='pinned constituent'):
        expand_sha([dict(profile='RVB23S64',extension='sha')],{'sha'})


def test_catalog_keeps_unassigned_checkers_visible():
    from rvw.formal.profile_clauses import catalogs
    row=dict(id='RVA23U64.base',text='Little endian.',checkers=[],tests=[],
             source=dict(path='profiles.adoc',sha256='hash',line=1))
    result=catalogs({'profiles':{'RVA23U64':{'obligations':[row]}}})
    assert result['hash']['unmapped_checkers']==['RVA23U64.base']
    assert result['hash']['obligations'][0]['checkers']==[]


def test_canonical_h_and_profile_implementation_declarations(tmp_path):
    import json
    from rvw.formal.profiles import assess,sha
    from rvw.cov.isa import extensions
    assert extensions('rv64ih')==(64,{'i','h'})
    text='''=== RVA23U64 Profile
==== RVA23U64 Mandatory Base
RV64I is mandatory and little-endian. ECALL requests a trap.
==== RVA23U64 Mandatory Extensions
- *M* Multiply.
=== RVA23S64 Profile
==== RVA23S64 Mandatory Extensions
- *Sha* Augmented hypervisor.
*Sha* comprises the following extensions:
** *H* Hypervisor.
** *Ssstateen* State enable.
=== RVB23U64 Profile
==== RVB23U64 Mandatory Base
RV64I is mandatory and little-endian.
==== RVB23U64 Mandatory Extensions
- *M* Multiply.
=== RVB23S64 Profile
==== RVB23S64 Optional Extensions
- *Sha* Augmented hypervisor.
- If the hypervisor extension is implemented and pointer masking
  (Ssnpm) is supported then henvcfg.PMM must support PMLEN=0 and 7.
'''
    source=tmp_path/'profiles.adoc';source.write_text(text)
    isa=tmp_path/'isa.json';isa.write_text(json.dumps(dict(schema='rvw.isa/1',isa='rv64ih_sha_ssnpm',
        extensions={name:{'version':None} for name in ('i','h','sha','ssnpm')},options={})))
    plan=dict(schema='rvw.profile-plan/1',isa_manifest='isa.json',profiles=['RVA23U64','RVB23S64'],
              documents=[dict(path='profiles.adoc',sha256=sha(source.read_bytes()))])
    path=tmp_path/'plan.json';path.write_text(json.dumps(plan))
    report=assess(path)
    user=report['profiles']['RVA23U64'];supervisor=report['profiles']['RVB23S64']
    assert 'RVA23U64.base' in user['missing']
    assert 'RVB23S64.h' in supervisor['implemented']
    assert 'RVB23S64.ssstateen' in supervisor['missing']
    assert 'RVB23S64.hypervisor_pointer_mask' in supervisor['missing']
    plan['declarations']={'RVA23U64.base':True,'RVB23S64.hypervisor_pointer_mask':True}
    path.write_text(json.dumps(plan));report=assess(path)
    assert 'RVA23U64.base' in report['profiles']['RVA23U64']['implemented']
    assert 'RVB23S64.hypervisor_pointer_mask' in report['profiles']['RVB23S64']['implemented']
    assert not report['profiles']['RVB23S64']['verified']


def test_index_materialization_checks_source_and_span(tmp_path):
    import hashlib
    import pytest
    from rvw.formal.profile_clauses import materialize
    source=tmp_path/'profiles.adoc';source.write_text('Mandatory clause.\n')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    row=dict(id='profile.base',source_sha256=digest,line=1,end_line=1,
             obligation_sha256=hashlib.sha256(b'Mandatory clause.').hexdigest(),checkers=[],tests=[])
    index=dict(schema='rvw.profile-source-index/1',sources=[dict(name=source.name,sha256=digest)],obligations=[row])
    assert materialize(index,tmp_path)[digest]['unmapped_checkers']==['profile.base']
    row['end_line']=2
    with pytest.raises(ValueError,match='span'):materialize(index,tmp_path)
    row['end_line']=1;source.write_text('Changed clause.\n')
    with pytest.raises(ValueError,match='hash'):materialize(index,tmp_path)


def test_seed_index_shape_and_pinned_materialization():
    import json,os
    import pytest
    from rvw.formal.profile_clauses import materialize
    root=Path(__file__).resolve().parents[2]
    index=json.loads((root/'examples/profiles/source-index.json').read_text())
    assert len(index['obligations'])==273
    assert {row['profile'] for row in index['obligations']}=={'RVA23U64','RVA23S64','RVB23U64','RVB23S64'}
    checkout=os.environ.get('RISCV_PROFILES')
    if not checkout:
        pytest.skip('pinned riscv-profiles source required for span verification')
    result=materialize(index,Path(checkout)/'src')
    assert len(result)==2
    assert sum(len(row['obligations']) for row in result.values())==273
