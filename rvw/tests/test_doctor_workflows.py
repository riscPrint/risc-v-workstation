"""Optional regression and gate inputs must not block unrelated workflows."""
from types import SimpleNamespace
import pytest
from rvw.doctor.check import workflow_readiness

pytestmark = pytest.mark.fast


def test_optional_suite_and_dirty_tree_do_not_block_run():
    rows = [dict(name=n, status='ready', fix='') for n in ('python', 'project', 'native.sim', 'adapter.info')]
    rows.extend([dict(name='suite.optional', status='warning', fix='build ELFs'),
                 dict(name='gate.core', status='inconclusive', fix='review changes')])
    project = SimpleNamespace(sections={'query': {'build': 'fixture'}})
    report = workflow_readiness(rows, project, ['sim'])
    assert report['run']['status'] == 'ready'
    assert report['regress']['status'] == 'ready'
    assert report['regress:optional']['status'] == 'not_ready'
    assert report['gate']['status'] == 'inconclusive'
    assert report['query']['status'] == 'ready'
    assert report['formal']['status'] == 'not_configured'
    assert report['run']['qualification'] == 'setup_preconditions_only'


def test_unrequested_features_and_missing_evidence_do_not_claim_readiness():
    project = SimpleNamespace(sections={'cosim': {'platform': 'fixture'}, 'formal': {'top': 'fixture'}})
    rows = [dict(name=n, status='ready', fix='') for n in ('python', 'project', 'native.sim')]
    rows.append(dict(name='adapter.info', status='inconclusive', fix='run adapter info'))
    report = workflow_readiness(rows, project, ['sim'])
    assert report['run']['status'] == 'inconclusive'
    assert report['cosim']['status'] == report['formal']['status'] == 'not_checked'


def test_build_only_suite_is_not_checked_for_elf_files(tmp_path, monkeypatch):
    import json
    from rvw.doctor import check
    project = SimpleNamespace(path=tmp_path / 'rvw.toml', root=tmp_path,
                              get=lambda *a: None, sections={})
    cfg = SimpleNamespace(adapter=['fixture'], path=project.path, name='fixture',
                          configs=['default'], default_config='default', build_timeout_s=10,
                          suites={'elaboration': SimpleNamespace(kind='build')}, input_complete=False,
                          identity=False, identity_capture=False, source_repo=tmp_path)
    monkeypatch.setattr(check, 'load_project', lambda p: project)
    monkeypatch.setattr(check, 'load_config', lambda **kw: cfg)
    def run(cmd, **kw):
        output = 'PRESENT Verilator: 5.052\n'
        if 'info' in cmd:
            output = json.dumps(dict(schema='rvw.adapter/1', core='fixture', configs=['default'],
                                     default_config='default', xlen=32, isa={'default': 'rv32im'}))
        return SimpleNamespace(returncode=0, stdout=output, stderr='')
    monkeypatch.setattr(check, 'run_group', run)
    result = check.diagnose(project=tmp_path, features='sim')
    row = next(c for c in result['checks'] if c['name'] == 'suite.elaboration')
    assert row['status'] == 'ready'
    assert 'build-only' in row['detail']
    assert result['status'] == 'ready'  # No smoke request; gate remains inconclusive.


def test_missing_optional_suite_does_not_block_quick_tier():
    rows = [dict(name=n, status='ready', fix='') for n in
            ('python', 'project', 'native.sim', 'adapter.info', 'suite.smoke')]
    rows.append(dict(name='suite.optional', status='warning', fix='build optional ELFs'))
    cfg = SimpleNamespace(tiers={'quick': SimpleNamespace(runs=[SimpleNamespace(suite='smoke')])})
    result = workflow_readiness(rows, SimpleNamespace(sections={}), ['sim'], cfg)
    assert result['regress:tier:quick']['status'] == 'ready'
    assert result['gate:tier:quick']['status'] == 'ready'
    assert result['regress:optional']['status'] == 'not_ready'


def test_skipping_info_cannot_hide_an_explicit_smoke_request(tmp_path):
    from rvw.doctor.check import diagnose
    result = diagnose(project=tmp_path, skip_adapter_info=True, smoke_elf='smoke')
    assert result['exit_code'] == 2
    assert '--skip-adapter-info' in result['error']
