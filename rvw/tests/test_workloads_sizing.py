"""Input variants retain source pins and carry executable checks."""
import importlib.util
from pathlib import Path
import pytest
from rvw.workloads.core import ASSETS, tree_hash
pytestmark = pytest.mark.fast

spec = importlib.util.spec_from_file_location('rtl_recipe', ASSETS / 'rtl_recipe.py')
recipe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recipe)


def source_tree(tmp_path, bench):
    source = tmp_path / 'source'
    (source / 'env').mkdir(parents=True)
    (source / 'benchmarks/common').mkdir(parents=True)
    (source / 'benchmarks/common/crt.S').write_text('original')
    (source / 'benchmarks' / bench).mkdir()
    return source


def test_sort_prefix_and_expected_values(tmp_path):
    source = source_tree(tmp_path, 'qsort')
    (source / 'benchmarks/qsort/dataset1.h').write_text(
        'type input_data[DATA_SIZE] = {8,3,1,5};')
    before = tree_hash(source)
    out = tmp_path / 'out'; out.mkdir()
    result = recipe.prepare(source, out, 'qsort', {'SORT_SIZE': '3'})
    text = (result / 'qsort/dataset1.h').read_text()
    assert 'input_data[DATA_SIZE] = {8,3,1}' in text
    assert 'verify_data[DATA_SIZE] = {1,3,8}' in text
    assert tree_hash(source) == before


def test_checker_and_csr_free_start(tmp_path):
    source = source_tree(tmp_path, 'dhrystone')
    (source / 'benchmarks/dhrystone/dhrystone_main.c').write_text(
        'if (User_Time < Too_Small_Time) {}\n  return 0;')
    (source / 'benchmarks/dhrystone/dhrystone.h').write_text('#define NUMBER_OF_RUNS 500\n#define Start_Timer() read_csr(mcycle)\n#define Other_Timer() read_csr(minstreth)')
    out = tmp_path / 'out'; out.mkdir()
    result = recipe.prepare(source, out, 'dhrystone', {'RUNTIME': 'user-counters', 'DHRYSTONE_RUNS': '10'})
    assert 'csrr' not in (result / 'common/crt.S').read_text()
    text = (result / 'dhrystone/dhrystone_main.c').read_text()
    assert 'return Int_Glob != 5' in text
    assert 'strcmp(Str_2_Loc' in text
    assert 'if (0)' in text
    header = (result / 'dhrystone/dhrystone.h').read_text()
    assert '#define NUMBER_OF_RUNS 10' in header
    assert 'read_csr(cycle)' in header
    assert 'read_csr(instreth)' in header
    assert 'read_csr(mcycle)' not in header


def test_spmv_keeps_the_pinned_expected_prefix(tmp_path):
    source = source_tree(tmp_path, 'spmv')
    text = '#define R 500\nconst double verify_data[500] = {1,2,3};\n'
    (source / 'benchmarks/spmv/dataset1.h').write_text(text)
    out = tmp_path / 'out'; out.mkdir()
    result = recipe.prepare(source, out, 'spmv', {'SPMV_ROWS': '8'})
    assert (result / 'spmv/dataset1.h').read_text() == text.replace('R 500', 'R 8')


def test_counter_free_runtime_removes_guest_timer_reads(tmp_path):
    source = source_tree(tmp_path, 'dhrystone')
    (source / 'benchmarks/dhrystone/dhrystone_main.c').write_text(
        'if (User_Time < Too_Small_Time) {}\n  Microseconds = (User_Time / Number_Of_Runs);\n'
        '  printf("Microseconds for one run through Dhrystone: %ld", Microseconds);\n  return 0;')
    (source / 'benchmarks/dhrystone/dhrystone.h').write_text(
        '#define NUMBER_OF_RUNS 500\n#define Start_Timer() read_csr(mcycle)\n')
    out = tmp_path / 'out'; out.mkdir()
    result = recipe.prepare(source,out,'dhrystone',{'RUNTIME':'no-counters'})
    assert 'read_csr(mcycle)' not in (result / 'dhrystone/dhrystone.h').read_text()
    assert 'Microseconds =' not in (result / 'dhrystone/dhrystone_main.c').read_text()
    assert 'return Int_Glob != 5' in (result / 'dhrystone/dhrystone_main.c').read_text()
