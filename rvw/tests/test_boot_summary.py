"""Cumulative boot counters require every slice's wall time exactly once."""
import importlib.util
import json
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
PATH = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/linux/summary.py'
spec = importlib.util.spec_from_file_location('boot_summary', PATH)
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


def reports(tmp_path):
    paths = []
    for n, total, count, seconds in [('1', 20, 7, 1.0), ('2', 40, 18, 2.0)]:
        path = tmp_path / f'{n}.json'
        path.write_text(json.dumps(dict(schema='rvw.vexii-boot-slice-result/1', cycle=str(total),
            retired=str(count), slice_cycles='20', slice_retired='7' if n == '1' else '11',
            wall_seconds=seconds, status='bounded', console={'uart': ''})))
        paths.append(path)
    return paths


def test_contiguous_wall_sum_and_rates(tmp_path):
    paths = reports(tmp_path)
    result = summary.summarize(paths[::-1])
    assert result['cycles'] == 40 and result['retired'] == 18
    assert result['wall_seconds'] == 3.0 and result['instructions_per_second'] == 6.0
    assert not result['userspace_marker'] and result['status'] == 'bounded'
    final = json.loads(paths[-1].read_text())
    final.update(status='shutdown', console={'uart': 'RVW_LINUX_USERSPACE\r\n'},
                 retired_by_mode=['21', '0', '0', '0'])
    paths[-1].write_text(json.dumps(final))
    result = summary.summarize(paths)
    assert result['userspace_marker'] and result['status'] == 'shutdown'
    assert result['user_retirements'] == 21


def test_missing_or_duplicate_slice_is_refused(tmp_path):
    paths = reports(tmp_path)
    for selection in (paths[1:], paths+paths[:1]):
        with pytest.raises(ValueError, match='contiguous history'):
            summary.summarize(selection)
