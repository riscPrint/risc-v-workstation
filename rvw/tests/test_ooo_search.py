import json
import sqlite3
from dataclasses import asdict
from rvw.ooo.core import Config
from rvw.ooo.search import search, frontier
from test_ooo import trace


def test_grid_and_bayesian_search(tmp_path):
    c = Config(4, 16, 4, 32, 4, 16, 4, 4, 4, {'alu': 1})
    (tmp_path / 'config.json').write_text(json.dumps(asdict(c)))
    trace(tmp_path / 'trace.jsonl')
    plan = dict(schema='rvw.ooo-search-plan/1', config='config.json', traces=['trace.jsonl'],
                parameters={'issue_width': [1, 2, 4]}, method='grid', budget=3, max_cycles=100,
                area=dict(base=10, coefficients={'issue_width': 2}, source='project estimate'))
    p = tmp_path / 'plan.json'
    for method in ('grid', 'bayesian'):
        plan['method'] = method
        p.write_text(json.dumps(plan))
        out = tmp_path / method
        r = search(p, out)
        assert len(r['points']) == 3
        assert r['objectives'] == ['cycles', 'area']
        assert r['unobserved'] == ['power']
        assert r['accuracy_status'] == 'inconclusive'
        assert len(set(point['id'] for point in r['points'])) == 3
        with sqlite3.connect(out / 'results.sqlite') as db:
            assert db.execute('SELECT count(*) FROM points').fetchone()[0] == 3


def test_pareto_dominance_preserves_tradeoffs():
    rows = [dict(id=0, cycles=10, area=10), dict(id=1, cycles=8, area=12), dict(id=2, cycles=12, area=11)]
    assert frontier(rows, ['cycles', 'area']) == [0, 1]
