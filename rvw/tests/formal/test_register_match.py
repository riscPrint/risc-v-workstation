from rvw.formal.equiv import mapping


def test_relocated_state_matches_without_manual_pairs():
    rows, missing = mapping({'old.saved': (1, 2)}, {'new.saved': (5, 6)}, [])
    assert rows == [{'gold': 'old.saved', 'gate': 'new.saved', 'width': 2, 'method': 'unique_leaf'}]
    assert not any(missing.values())


def test_ambiguous_or_changed_width_is_not_matched():
    gold = {'a.saved': (1, 2), 'b.saved': (3, 4)}
    gate = {'c.saved': (5, 6)}
    assert mapping(gold, gate, [])[0] == []
    assert mapping({'a.saved': (1,)}, gate, [])[0] == []


def test_explicit_pair_has_priority():
    rows, missing = mapping({'a.saved': (1,), 'b.saved': (2,)},
                            {'c.saved': (3,), 'd.saved': (4,)}, ['a.saved=d.saved'])
    assert rows[0]['method'] == 'manual'
    assert rows[1] == {'gold': 'b.saved', 'gate': 'c.saved', 'width': 1, 'method': 'unique_leaf'}
    assert not any(missing.values())


def test_relocated_registers_still_require_output_proof(tmp_path):
    import json
    import shutil
    import pytest
    from rvw.cli import main
    if not all(shutil.which(t) for t in ('yosys', 'eqy', 'sby', 'yosys-abc', 'yices-smt2')):
        pytest.skip('needs native equivalence tools')
    leaf = 'module leaf(input clk,a,output q); reg saved; always @(posedge clk) saved<=a; assign q=~saved; endmodule\n'
    a, b = tmp_path/'gold.v', tmp_path/'gate.v'
    top = 'module top(input clk,a,output q); leaf INSTANCE(clk,a,q); endmodule'
    a.write_text(leaf+top.replace('INSTANCE', 'before_move'))
    for mutant in (False, True):
        b.write_text(leaf.replace('~saved', '(~saved ^ a)')+top.replace('INSTANCE','after_move') if mutant else leaf+top.replace('INSTANCE','after_move'))
        out = tmp_path/str(mutant)
        main(['formal','equiv','--gold',str(a),'--gate',str(b),'--top','top','--settle','1','--out',str(out)])
        result = json.loads((out/'result.json').read_text())
        assert result['status'] == ('not_equivalent' if mutant else 'equivalent'), result
        assert any(row['method']=='unique_leaf' for row in result['state_mapping'])
