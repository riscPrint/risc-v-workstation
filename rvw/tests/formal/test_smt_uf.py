import pytest

pytestmark = pytest.mark.fast
from rvw.formal.smt_uf import transform


def test_global_function_and_metadata_preserved():
    text = '''; yosys-smt2-module top
(declare-fun |top#a| (State) (_ BitVec 8))
(declare-fun |top#b| (State) (_ BitVec 8))
; yosys-smt2-assert 0 source.sv:1
(define-fun |top#mul| ((state State)) (_ BitVec 8) (bvmul (|top#a| state) (|top#b| state)))
(define-fun |top#other| ((state State)) (_ BitVec 8) (bvmul (|top#b| state) (|top#a| state)))
'''
    out, functions = transform(text)
    assert out.count('(declare-fun rvw_uf_bvmul_8 ') == 1
    assert functions[0]['occurrences'] == 2
    assert '; yosys-smt2-assert 0 source.sv:1' in out
    assert '(rvw_uf_bvmul_8 (|top#a| state)' in out


def test_input_width_not_extracted_result_width():
    text = '(define-fun f ((a (_ BitVec 16)) (b (_ BitVec 16))) (_ BitVec 8) ((_ extract 7 0) (bvmul a b)))'
    out, records = transform(text)
    assert records[0]['width'] == 16 and 'rvw_uf_bvmul_16' in out


def test_simultaneous_let_and_signed_operations():
    text = '(define-fun f ((a (_ BitVec 8))) (_ BitVec 16) (let ((x ((_ zero_extend 8) a))) (bvsdiv x (_ bv3 16))))'
    _, records = transform(text)
    assert records[0]['operator'] == 'bvsdiv' and records[0]['width'] == 16


def test_unknown_width_and_collision_fail_closed():
    with pytest.raises(ValueError, match='operand widths'):
        transform('(define-fun f ((s State)) (_ BitVec 8) (bvmul unknown unknown))')
    with pytest.raises(ValueError, match='collision'):
        transform('(declare-fun rvw_uf_bvmul_8 () (_ BitVec 8)) (define-fun f ((a (_ BitVec 8))) (_ BitVec 8) (bvmul a a))')


def test_no_operator_is_identity():
    text = '; source metadata\n(define-fun f () (_ BitVec 4) #b1010)\n'
    assert transform(text) == (text, [])


def test_sort_aliases_array_widths_and_simultaneous_bindings():
    text = '(declare-fun mem (State) (Array (_ BitVec 4) (_ BitVec 8))) (define-fun f ((s State)) (_ BitVec 8) (bvmul (select (mem s) #b0011) #x02))'
    out, records = transform(text)
    assert records[0]['width'] == 8
    assert '(define-sort rvw_uf_bits_8 () (_ BitVec 8))' in out
    assert '(rvw_uf_bits_8 rvw_uf_bits_8)' in out
    _, records = transform('(define-fun f ((a (_ BitVec 8))) (_ BitVec 8) (let ((a ((_ zero_extend 8) a)) (b (bvmul a a))) b))')
    assert records[0]['width'] == 8


def test_comments_strings_and_sort_collisions():
    text = '; bvmul must stay in this comment\n(set-info :source "(bvmul untouched)")\n(define-fun f ((a (_ BitVec 8))) (_ BitVec 8) (bvmul a a))'
    out, _ = transform(text)
    assert '; bvmul must stay in this comment' in out
    assert '(set-info :source "(bvmul untouched)")' in out
    with pytest.raises(ValueError, match='sort name collision'):
        transform('(define-sort rvw_uf_bits_8 () (_ BitVec 8)) (define-fun f ((a (_ BitVec 8))) (_ BitVec 8) (bvmul a a))')


def test_file_rewrite_is_idempotent_and_retains_evidence(tmp_path):
    import json
    from rvw.formal.smt_uf import rewrite_file
    path = tmp_path / 'model.smt2'
    path.write_text('(define-fun f ((a (_ BitVec 8))) (_ BitVec 8) (bvmul a a))')
    rewrite_file(path, ['bvmul'])
    first = path.read_bytes()
    metadata = path.with_suffix('.smt2.rvw-uf.json')
    recorded = metadata.read_bytes()
    rewrite_file(path, ['bvmul'])
    assert path.read_bytes() == first and metadata.read_bytes() == recorded
    assert json.loads(recorded)['functions'][0]['occurrences'] == 1


