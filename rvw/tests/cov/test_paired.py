"""Plots must preserve credited measurements and reject incompatible contexts."""
from copy import deepcopy
import json
import xml.etree.ElementTree as ET
import pytest
from rvw.cov.paired import compare

pytestmark = pytest.mark.fast


def reports():
    report = dict(pair_context='same-inputs', supported_bins=3, full_plan_bins=10, generation_groups=[],
                  implementation_sha256='fixture', execution_identity='fixture-native',
                  initial_hits=['a'], hits=['a','b'], attempt_budget=2, status='inconclusive',
                  strategy='directed', initial={'records':[]}, attempts=[
                      dict(status='hit', elapsed_s=2.0, new_hits=['b']),
                      dict(status='compile_error', elapsed_s=1.0, new_hits=[])])
    random = deepcopy(report); random['strategy'] = 'random'
    random['attempts'][0]['elapsed_s'] = 3.0
    return report, random


def test_curves_use_only_credited_hits_and_keep_failed_cost(tmp_path):
    directed, random = reports()
    result = compare(directed, random, tmp_path/'curve')
    assert result['arms']['directed']['points'] == [
        {'attempt':0, 'elapsed_s':0.0, 'bins':1},
        {'attempt':1, 'elapsed_s':2.0, 'bins':2},
        {'attempt':2, 'elapsed_s':3.0, 'bins':2}]
    assert json.loads((tmp_path/'curve/curves.json').read_text()) == result
    assert len(ET.parse(tmp_path/'curve/curves.svg').findall('{http://www.w3.org/2000/svg}polyline')) == 2


@pytest.mark.parametrize('field', ['pair_context','supported_bins','execution_identity','implementation_sha256','initial_hits','attempt_budget'])
def test_incompatible_campaigns_refuse_comparison(tmp_path, field):
    directed, random = reports(); random[field] = 'different'
    with pytest.raises(ValueError, match='differ|incompatible'):
        compare(directed, random, tmp_path/'curve')
    assert not (tmp_path/'curve').exists()


def test_unqualified_hits_cannot_be_plotted(tmp_path):
    directed, random = reports(); directed['attempts'][1]['new_hits'] = ['c']
    with pytest.raises(ValueError, match='unqualified'):
        compare(directed, random, tmp_path/'curve')


@pytest.mark.parametrize('cost', [None, -1, float('nan'), float('inf'), True])
def test_unknown_or_invalid_cost_cannot_be_plotted(tmp_path, cost):
    directed, random = reports()
    directed['attempts'][0]['elapsed_s'] = cost
    with pytest.raises(ValueError, match='cost'):
        compare(directed, random, tmp_path/'curve')
    assert not (tmp_path/'curve').exists()
