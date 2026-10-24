import json
from pathlib import Path
import subprocess

import pytest

from rvw.cov.code import iter_dat, merge, rank, report, select
from rvw.cli import main


def dat(path, values, file='logic.v'):
    path.write_text('# SystemC::Coverage-3\n' + ''.join(
        f"C '\x01f\x02{file}\x01l\x02{n}\x01page\x02v_line/Unit\x01h\x02TOP.unit' {count}\n"
        for n, count in enumerate(values, 1)))
    return path


def test_points_merge_exact_and_no_silent_incompatible_merge(tmp_path):
    a, b = dat(tmp_path / 'a.dat', [1, 0, 2]), dat(tmp_path / 'b.dat', [0, 4, 1])
    data = merge([f'A={a}', f'B={b}'])
    assert [p['count'] for p in data['points']] == [1, 4, 3]
    assert report(data)['summary']['hit'] == 3
    assert report(data)['module_types']['Unit']['unknown']['hit'] == 3
    assert rank(data, exact=True)['selected'] == ['A', 'B']
    assert sum(row[3] for row in iter_dat(a)) == 3
    dat(b, [0, 4])
    with pytest.raises(ValueError, match='universes differ'):
        merge([f'A={a}', f'B={b}'])
    with pytest.raises(ValueError, match='duplicate test'):
        merge([f'A={a}', f'A={a}'])


def test_mapping_is_exact_not_nearest_and_hierarchy_warns(tmp_path):
    (tmp_path / 'logic.v').write_text('// Somewhere.scala:9\nassign x=y;\n')
    data = merge([str(dat(tmp_path / 'test.dat', [0, 1]))], tmp_path)
    assert data['points'][0]['scala']['line'] == 9
    assert data['points'][1]['scala'] is None
    data['points'][0]['fields']['h'] = 'TOP.*.unit'
    assert report(data)['warnings']


def test_scala_comment_resolution_requires_a_unique_filename(tmp_path):
    source = tmp_path / 'scala'
    source.mkdir()
    (source / 'Unit.scala').write_text('class Unit\n')
    (tmp_path / 'logic.v').write_text('assign a=b; // @ Unit.scala l1\n')
    args = [str(dat(tmp_path / 'a.dat', [1]))]
    data = merge(args, tmp_path, scala_root=source)
    assert data['points'][0]['scala']['file'] == str(source / 'Unit.scala')
    (source / 'nested').mkdir()
    (source / 'nested/Unit.scala').write_text('class Unit\n')
    data = merge(args, tmp_path, scala_root=source)
    assert data['points'][0]['scala'] is None


@pytest.mark.parametrize('explicit', [
    'vendor/Unit.scala', './Unit.scala', '../vendor/Unit.scala', '/vendor/Unit.scala',
    r'vendor\Unit.scala',
])
def test_scala_comment_resolution_preserves_explicit_paths(tmp_path, explicit):
    source = tmp_path / 'scala'
    source.mkdir()
    (source / 'Unit.scala').write_text('class Unit\n')
    (tmp_path / 'logic.v').write_text(f'assign a=b; // @ {explicit}:42\n')
    data = merge([str(dat(tmp_path / 'a.dat', [1]))], tmp_path, scala_root=source)
    assert data['points'][0]['scala']['locations'] == [{'file': explicit, 'line': 42}]


def test_ambiguous_bare_comment_refuses_the_whole_span(tmp_path):
    source = tmp_path / 'scala'
    for folder in ('one', 'two'):
        (source / folder).mkdir(parents=True)
        (source / folder / 'Unit.scala').write_text('class Unit\n')
    (tmp_path / 'logic.v').write_text('assign a=b; // @ vendor/Other.scala:1\n'
                                     'assign c=d; // @ Unit.scala:42\n')
    from rvw.cov.code import SourceMap
    assert SourceMap(tmp_path, scala_root=source).location({'f': 'logic.v', 'l': '1', 'S': '1-2'}) is None


def test_verilator_statement_spans_map_all_comments_but_not_neighbors(tmp_path):
    from rvw.cov.code import SourceMap
    (tmp_path / 'logic.v').write_text('always @(*) begin\n x = y; // @ Unit.scala l42\n'
                                     ' z = w; // @ Other.scala l9\nend\n // @ Unrelated.scala l70\n')
    source = SourceMap(tmp_path)
    location = source.location({'f': 'logic.v', 'l': '1', 'S': '1-3'})
    assert location['method'] == 'covered-span-comments'
    assert location['locations'] == [{'file': 'Other.scala', 'line': 9}, {'file': 'Unit.scala', 'line': 42}]
    assert source.location({'f': 'logic.v', 'l': '4'}) is None


def test_c1_c3_inputs(tmp_path):
    dat(tmp_path / 'coverage.dat', [1])
    run = {"schema": "rvw.run/1", "status": "pass", "elf": "add", "artifacts": {"coverage": "coverage.dat"}}
    (tmp_path / 'result.json').write_text(json.dumps(run))
    assert list(merge([str(tmp_path)])['tests']) == ['add']
    suite = {"schema": "rvw.results/1", "run_id": "test", "suite": "isa", "core": "test", "config": "tiny", "created": "now", "source": {},
             "tests": [{"id": "addition", "status": "pass", "run": "result.json"}]}
    (tmp_path / 'results.json').write_text(json.dumps(suite))
    assert list(merge([str(tmp_path)])['tests']) == ['addition']


def test_selection_uses_base_hunks_and_falls_back_for_new_code(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    source = tmp_path / 'Unit.scala'
    source.write_text('val a=1\nval b=2\n')
    def commit():
        subprocess.run(['git', '-C', str(tmp_path), 'add', 'Unit.scala'], check=True)
        subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test', '-c', 'user.email=t@x',
                        'commit', '-qm', 'test'], check=True)
    commit()
    source.write_text('val a=3\nval b=2\n')
    commit()
    data = merge([f'A={dat(tmp_path / "a.dat", [1, 0])}', f'B={dat(tmp_path / "b.dat", [0, 1])}'])
    data['source_revision'] = subprocess.run(['git', '-C', str(tmp_path), 'rev-parse', 'HEAD~1'],
                                             check=True, capture_output=True, text=True).stdout.strip()
    for p in data['points']:
        p['scala'] = {"file": "Unit.scala", "line": int(p['fields']['l'])}
    result = select(data, 'HEAD~1..HEAD', tmp_path)
    assert result['tests'] == ['A']
    assert not result['fallback_all']
    data['points'][0]['scala'] = None
    assert select(data, 'HEAD~1..HEAD', tmp_path)['tests'] == ['A', 'B']
    data['points'][0]['scala'] = {"file": "Unit.scala", "line": 1}
    data['tests']['A']['run'] = {"schema": "rvw.run/1", "status": "pass",
                                "source": {"core_rev": data['source_revision']}}
    result = select(data, 'HEAD~1..HEAD', tmp_path)
    assert result['fallback_all'] and result['source_clean_unverified']
    data['tests']['A']['run']['source']['core_dirty'] = False
    assert select(data, 'HEAD~1..HEAD', tmp_path)['tests'] == ['A']


def test_json_error_surface(capsys):
    assert main(['cov', 'report', 'missing.json', '--json']) == 3
    assert json.loads(capsys.readouterr().out)['schema'] == 'rvw.coverage-error/1'


def test_exact_cover_beats_greedy_and_empty(tmp_path):
    # Greedy first chooses A; optimal uses B+C. Pruning also removes A later.
    data = merge([f'{n}={dat(tmp_path / (n+".dat"), counts)}' for n, counts in
                  [('A', [1, 1, 1, 1, 0, 0]), ('B', [1, 1, 0, 0, 1, 0]), ('C', [0, 0, 1, 1, 0, 1])]])
    assert rank(data, exact=True)['selected'] == ['B', 'C']
    assert rank(data)['selected'] == ['B', 'C']
    empty = merge([str(dat(tmp_path / 'empty.dat', [0, 0]))])
    assert rank(empty, exact=True)['selected'] == []


def test_streaming_merge_aggregates_duplicate_records(tmp_path):
    a = dat(tmp_path / 'a.dat', [2])
    a.write_text(a.read_text() + a.read_text().splitlines()[1] + '\n')
    b = dat(tmp_path / 'b.dat', [3])
    result = merge([f'A={a}', f'B={b}'])
    assert result['points'][0]['count'] == 7
    assert result['points'][0]['tests'] == {'A': 4, 'B': 3}


def test_source_paths_are_canonical_for_proof_identity(tmp_path):
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'logic.v').write_text('assign a=b; // @ Unit.scala l1\n')
    file = dat(tmp_path / 'a.dat', [0], file='sub/../logic.v')
    result = merge([str(file)], tmp_path)
    assert result['sources']['sub/../logic.v']['path'] == str(tmp_path / 'logic.v')
    assert result['points'][0]['scala']['line'] == 1


def test_selection_falls_back_for_non_scala_and_empty_diffs(tmp_path):
    # Review finding: a diff touching only a Verilog blackbox or build.sbt selected zero tests.
    git = lambda *a: subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test', '-c', 'user.email=t@x', *a],
                                    check=True, capture_output=True, text=True).stdout.strip()  # noqa: E731
    git('init', '-q')
    (tmp_path / 'Unit.scala').write_text('val a=1\nval b=2\n')
    (tmp_path / 'blackbox.v').write_text('module bb; endmodule\n')
    git('add', '.')
    git('commit', '-qm', 'base')
    base = git('rev-parse', 'HEAD')
    data = merge([f'A={dat(tmp_path / "a.dat", [1, 0])}', f'B={dat(tmp_path / "b.dat", [0, 1])}'])
    data['source_revision'] = base
    for p in data['points']:
        p['scala'] = {"file": "Unit.scala", "line": int(p['fields']['l'])}
    (tmp_path / 'blackbox.v').write_text('module bb(input a); endmodule\n')
    git('commit', '-qam', 'verilog only')
    result = select(data, 'HEAD~1..HEAD', tmp_path)
    assert result['fallback_all'] and result['tests'] == ['A', 'B']
    assert result['non_scala_changes'] == ['blackbox.v'] and 'non_scala_changes' in result['fallback_reasons']
    git('commit', '-q', '--allow-empty', '-m', 'empty')
    result = select(data, 'HEAD~1..HEAD', tmp_path)
    assert result['fallback_all'] and result['tests'] == ['A', 'B']
    assert 'empty_diff_between_revisions' in result['fallback_reasons']
    # The same revision on both sides changes nothing: no test is needed.
    result = select(data, 'HEAD..HEAD', tmp_path)
    assert not result['fallback_all'] and result['tests'] == []
    # A Scala file whose only change is its mode has no hunk to map.
    (tmp_path / 'Unit.scala').chmod(0o755)
    git('commit', '-qam', 'mode only')
    result = select(data, 'HEAD~1..HEAD', tmp_path)
    assert result['fallback_all'] and result['uncovered_changes'][0]['no_hunk']


def test_selection_needs_evidence_for_every_changed_line(tmp_path):
    # Round 10: one covered line in a hunk vouched for the whole hunk (probe_select.py).
    git = lambda *a: subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Test', '-c', 'user.email=t@x', *a],
                                    check=True, capture_output=True, text=True).stdout.strip()  # noqa: E731
    git('init', '-q')
    unit = tmp_path / 'Unit.scala'
    unit.write_text('val a = io.x + 1\nval b = io.y + 1\nval c = io.z + 1\n')
    git('add', '.')
    git('commit', '-qm', 'base')
    base = git('rev-parse', 'HEAD')

    def data(points):
        return {'source_revision': base, 'tests': {'A': {}, 'B': {}, 'C': {}},
                'points': [{'id': str(i), 'scala': {'file': 'Unit.scala', 'line': line}, 'tests': tests}
                           for i, (line, tests) in enumerate(points)]}

    def change(text):
        unit.write_text(text)
        git('commit', '-qam', 'change')
        return lambda d: select(d, 'HEAD~1..HEAD', tmp_path)

    # Lines 1-2 change in one hunk; line 2 has no mapping.
    run = change('val a = io.x + 2\nval b = io.y + 2\nval c = io.z + 1\n')
    r = run(data([(1, {'A': 1}), (3, {'B': 1})]))
    assert r['fallback_all'] and r['tests'] == ['A', 'B', 'C'], r
    assert r['uncovered_changes'][0]['unmapped_lines'] == [2]
    # Line 2 mapped but never hit.
    r = run(data([(1, {'A': 1}), (2, {'B': 0})]))
    assert r['fallback_all'] and r['uncovered_changes'][0]['unhit_lines'] == [2], r
    # Every changed line mapped and hit: only those tests.
    r = run(data([(1, {'A': 1}), (2, {'B': 2}), (3, {'C': 1})]))
    assert not r['fallback_all'] and r['tests'] == ['A', 'B'], r
    git('reset', '-q', '--hard', base)
    # A replacement hunk that adds a line: the added line has no BASE line to map.
    run = change('val a = io.x + 2\nval a2 = io.w\nval b = io.y + 1\nval c = io.z + 1\n')
    r = run(data([(1, {'A': 1}), (2, {'B': 1}), (3, {'C': 1})]))
    assert r['fallback_all'] and r['uncovered_changes'][0]['added_lines'] == 1, r
    git('reset', '-q', '--hard', base)
    # A pure insertion between two covered lines.
    run = change('val a = io.x + 1\nval new = io.w\nval b = io.y + 1\nval c = io.z + 1\n')
    r = run(data([(1, {'A': 1}), (2, {'B': 1}), (3, {'C': 1})]))
    assert r['fallback_all'] and r['uncovered_changes'][0]['insertion'], r
