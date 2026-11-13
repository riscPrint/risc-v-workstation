import json
import pytest
from rvw.cov.functional import functional
from .test_functional import row, trace, bins, decoded_observations_only


def run(tmp_path, rows, distances=None):
    config = tmp_path / 'plan.json'
    config.write_text(json.dumps({'groups': [], 'sequences': {'distances': distances or [1, 2]}}))
    return functional([trace(tmp_path / 'trace.jsonl', rows)], config)


def test_register_pairs_and_x0(tmp_path):
    result = run(tmp_path, [row(0, 0x002081b3, rd=3), # add x3,x1,x2
                            row(1, 0x00308133, rd=2), # add x2,x1,x3: RAW/WAR
                            row(2, 0x002081b3, rd=3)])
    hits = bins(result, 'sequence')
    assert hits['RAW', 1] == 2
    assert hits['WAR', 1] == 2
    assert hits['WAW', 2] == 1
    assert ['branch-after-load', 1] in result['groups']['sequence']['holes']
    result = run(tmp_path, [row(0, 0x00000013, rd=0), row(1, 0x00000013, rd=0)])
    assert bins(result, 'sequence') == {}


def test_memory_branch_and_boundaries(tmp_path):
    rows = [row(0, 0x00002083), row(1, 0x00008063, rd=0),
            row(2, 0x00002083), row(3, 0x00102023, rd=0)]
    hits = bins(run(tmp_path, rows), 'sequence')
    assert hits['branch-after-load', 1] == 1
    assert hits['store-after-load', 1] == 1
    assert hits['load-after-load', 2] == 1
    for boundary in ({'event':'trap','cause':'0x2'}, row(1, 0xffffffff, rd=0)):
        assert not bins(run(tmp_path, [rows[0], boundary, row(2, 0x00008063, rd=0)]), 'sequence')
    assert not bins(run(tmp_path, [rows[0], row(9, 0x00008063, rd=0)]), 'sequence')


def test_invalid_distances(tmp_path):
    with pytest.raises(ValueError, match='distances'):
        run(tmp_path, [], [0])


def test_control_flow_and_selected_kinds(tmp_path):
    config = tmp_path / 'selected.json'
    config.write_text(json.dumps({'groups': [], 'sequences': {
        'distances': [1], 'kinds': ['jump-after-branch']}}))
    rows = [row(0, 0x00008063, rd=0), row(1, 0x0000006f, rd=0)]
    r = functional([trace(tmp_path / 'selected.jsonl', rows)], config)
    assert bins(r, 'sequence') == {('jump-after-branch', 1): 1}
    assert r['groups']['sequence']['expected_bins'] == 1
