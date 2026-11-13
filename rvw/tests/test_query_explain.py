"""Self-explaining design diff: locations, covering tests and conservative fallback."""
import json
import subprocess
import sys

from rvw.query.explain import explain


def coverage(tmp_path, line, hits):
    data = {'schema': 'rvw.coverage/1', 'tests': ['t_gcd', 't_other'],
            'points': [{'id': 'p1', 'count': sum(hits.values()), 'tests': hits,
                        'scala': {'file': '/elsewhere/SpinalTrace/examples/src/spinaltrace/examples/Gcd.scala',
                                  'line': line}}]}
    p = tmp_path / 'cov.json'
    p.write_text(json.dumps(data))
    return str(p)


def test_logic_change_is_located_and_covered(gcd_db, buggy_db, tmp_path):
    r = explain(str(gcd_db), str(buggy_db), coverage(tmp_path, 20, {'t_gcd': 4, 't_other': 0}))
    logic = next(i for i in r['items'] if i['kind'] == 'logic')
    assert logic['path'] == 'x' and logic['change'] == 'changed'
    assert {'file': logic['locations'][0]['file'].rsplit('/', 1)[-1], 'line': 15} \
        == {'file': 'Gcd.scala', 'line': 15}
    assert any(l['line'] == 20 for l in logic['locations'])
    assert logic['tests'] == {'status': 'covered', 'mapped_points': 1, 'tests': ['t_gcd']}
    assert logic['effect']['status'] == 'unknown'
    # The renamed top component has no location: the selection falls back to every test.
    assert r['selection']['mode'] == 'all' and r['selection']['tests'] == ['t_gcd', 't_other']
    assert r['selection']['covering_tests'] == ['t_gcd'] and '<top>' in r['selection']['uncertain_items']
    assert r['effect']['status'] == 'not_measured'


def test_unhit_unmapped_and_effect(gcd_db, buggy_db, tmp_path):
    r = explain(str(gcd_db), str(buggy_db), coverage(tmp_path, 20, {'t_gcd': 0}))
    assert next(i for i in r['items'] if i['kind'] == 'logic')['tests']['status'] == 'unhit'
    r = explain(str(gcd_db), str(buggy_db), coverage(tmp_path, 99, {'t_gcd': 1}))
    assert next(i for i in r['items'] if i['kind'] == 'logic')['tests']['status'] == 'unmapped'
    eff = tmp_path / 'cmp.json'
    eff.write_text(json.dumps({'schema': 'rvw.perf.compare/1', 'differences': [{'metric': 'ipc', 'delta': -0.1}]}))
    r = explain(str(gcd_db), str(buggy_db), effect=str(eff))
    assert r['effect']['status'] == 'measured' and 'not attributed' in r['effect']['basis']
    assert next(i for i in r['items'] if i['kind'] == 'logic')['tests']['status'] == 'unknown'


def test_cli(gcd_db, buggy_db, tmp_path):
    out = subprocess.run([sys.executable, '-m', 'rvw', 'query', 'explain', str(gcd_db), str(buggy_db),
                          '--coverage', coverage(tmp_path, 20, {'t_gcd': 2})], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert 'test selection: all' in out.stdout and 'tests: covered t_gcd' in out.stdout
