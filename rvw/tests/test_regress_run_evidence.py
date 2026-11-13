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
