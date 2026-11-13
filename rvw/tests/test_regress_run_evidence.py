"""Owned result members exclude captured input fixtures with the same filename."""
from types import SimpleNamespace
import pytest
from rvw.regress import run_evidence as evidence
from rvw.results.generation import publish,open_current

pytestmark=pytest.mark.fast


def populate(directory):
    (directory/'result.json').write_text('{}')
    nested=directory/'input-capture';nested.mkdir()
    (nested/'result.json').write_text('{}')


def test_owned_c1_ignores_nested_input_results(tmp_path):
    populate(tmp_path)
    assert evidence.owned_run_paths(tmp_path)==[tmp_path/'result.json']


def test_sealed_c1_ignores_nested_input_results(tmp_path):
    publish(tmp_path,populate)
    generation=open_current(tmp_path)
    assert evidence.owned_run_paths(tmp_path)==[generation.path/'result.json']


def test_run_manifest_controls_c1_members(tmp_path,monkeypatch):
    (tmp_path/'run.json').write_text('{}')
    populate(tmp_path)
    suites=[SimpleNamespace(path=tmp_path/'suite',tests=[SimpleNamespace(run='test/result.json')])]
    monkeypatch.setattr(evidence,'load_run_set',lambda path:suites)
    assert evidence.owned_run_paths(tmp_path)==[tmp_path/'suite/test/result.json']


def test_run_paths_under_counts_each_regression_run_once(tmp_path):
    # A regression output keeps a sealed generation and the current view.
    root=tmp_path/'results'/'priv-rtl';root.mkdir(parents=True)
    def build(path):
        (path/'run.json').write_text('{}')
        (path/'suite/test').mkdir(parents=True)
        (path/'suite/test/result.json').write_text('{}')
    publish(root,build)
    build(root)
    other=tmp_path/'results'/'single';other.mkdir()
    populate(other)
    generation=open_current(root)
    suites=[SimpleNamespace(path=generation.path/'suite',tests=[SimpleNamespace(run='test/result.json')])]
    import rvw.regress.run_evidence as module
    original=module.load_run_set
    module.load_run_set=lambda path:suites
    try:
        paths=evidence.run_paths_under(tmp_path/'results')
    finally:
        module.load_run_set=original
    assert paths==[generation.path/'suite/test/result.json',other/'result.json']
    assert len(list((tmp_path/'results').rglob('result.json')))>len(paths)
