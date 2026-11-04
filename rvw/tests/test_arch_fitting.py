"""Synthetic event evidence, not a measured core calibration."""
import json
from pathlib import Path

import pytest

from rvw.arch import core
from rvw.arch.fitting import fit
from test_arch import reports, read_json, write_json


@pytest.fixture
def plan(reports, tmp_path):
    rtl, model = reports
    report = read_json(rtl)
    for row in report['benchmarks']:
        path = Path(row['evidence'])
        data = read_json(path)
        data['metrics']['branch_misses'] = 10
        write_json(path, data)
        row['evidence_sha256'] = core.digest(path.read_bytes())
    write_json(rtl, report)
    for row in read_json(model)['benchmarks']:
        Path(row['evidence']).with_name('stats.txt').write_text(
            '---------- Begin Simulation Statistics ----------\n'
            'system.cpu.branch_misses 12 # ROI event\n'
            'unused nan\n'
            '---------- End Simulation Statistics   ----------\n')
    names = [row['id'] for row in read_json(rtl)['benchmarks']]
    data = {'schema': 'rvw.arch-fit-plan/1', 'rtl': str(rtl),
            'candidates': {'synthetic': str(model)}, 'train': names[:1], 'held_out': names[1:],
            'events': [{'name': 'branch_misses', 'rtl_metric': 'branch_misses',
                        'gem5_stat': 'system.cpu.branch_misses', 'unit': 'count',
                        'semantics': 'Synthetic branch mispredictions in the ROI.'}],
            'scope': 'Synthetic counter test.', 'uncertainty': 'No hardware measured.',
            'unsupported': ['No predictor timing model.']}
    path = tmp_path / 'plan.json'
    write_json(path, data)
    return path


def test_fit_and_cli(plan, rvw):
    report = fit(plan)
    assert report['status'] == 'inconclusive'
    assert report['training_scores'] == {'synthetic': 0.35}
    assert report['held_out_score'] == 0.475
    assert rvw('arch', 'fit', plan, '--json')[2] == report


def test_holdout_does_not_select_candidate(plan):
    spec = read_json(plan)
    model = Path(spec['candidates']['synthetic'])
    clone = read_json(model)
    # A second candidate is perfect on training and worse on holdout.
    for index, row in enumerate(clone['benchmarks']):
        directory = plan.parent / f'candidate-{index}'
        directory.mkdir()
        new = directory / 'bare.json'
        new.write_bytes(Path(row['evidence']).read_bytes())
        row['evidence'] = str(new)
        new.with_name('stats.txt').write_text(
            '---------- Begin Simulation Statistics ----------\n'
            f'system.cpu.branch_misses {10 if index == 0 else 100}\n'
            '---------- End Simulation Statistics   ----------\n')
    write_json(plan.parent / 'second.json', clone)
    spec['candidates']['better-training'] = 'second.json'
    write_json(plan, spec)
    result = fit(plan)
    assert result['selected'] == 'better-training'
    assert result['held_out_score'] == 4.875


@pytest.mark.parametrize('mutation', ['overlap', 'missing', 'unknown', 'uncertainty', 'duplicate'])
def test_invalid_plan(plan, mutation):
    data = read_json(plan)
    if mutation == 'overlap': data['held_out'] = data['train']
    if mutation == 'missing': data['train'] = []
    if mutation == 'unknown': data['train'] = ['absent']
    if mutation == 'uncertainty': data['uncertainty'] = ''
    if mutation == 'duplicate': data['events'] *= 2
    write_json(plan, data)
    with pytest.raises(ValueError): fit(plan)


@pytest.mark.parametrize('value', ['nan', '-1', 'inf'])
def test_invalid_event(plan, value):
    model = read_json(Path(read_json(plan)['candidates']['synthetic']))
    path = Path(model['benchmarks'][0]['evidence']).with_name('stats.txt')
    path.write_text(path.read_text().replace('branch_misses 12', 'branch_misses ' + value))
    with pytest.raises(ValueError): fit(plan)


def test_missing_stats_is_not_zero(plan):
    model = read_json(Path(read_json(plan)['candidates']['synthetic']))
    Path(model['benchmarks'][0]['evidence']).with_name('stats.txt').unlink()
    with pytest.raises(OSError): fit(plan)


def test_real_gem5_distribution_columns(tmp_path):
    from rvw.arch.fitting import roi_stats
    path = tmp_path / 'stats.txt'
    path.write_text('---------- Begin Simulation Statistics ----------\n'
                    'system.cpu.numIssuedDist::underflows 0 0.00% 0.00% # Count\n'
                    '---------- End Simulation Statistics   ----------\n')
    assert roi_stats(path)[0]['system.cpu.numIssuedDist::underflows'] == '0'


def test_holdout_rejects_renamed_training_elf(plan):
    spec = read_json(plan)
    for report_path in (Path(spec['rtl']), Path(spec['candidates']['synthetic'])):
        report = read_json(report_path)
        train, held = report['benchmarks']
        held['elf'] = train['elf']
        held['elf_sha256'] = train['elf_sha256']
        if report['engine'] == 'rtl':
            evidence_path = Path(held['evidence'])
            evidence = read_json(evidence_path)
            evidence['elf_sha256'] = train['elf_sha256']
            write_json(evidence_path, evidence)
            held['evidence_sha256'] = core.digest(evidence_path.read_bytes())
        write_json(report_path, report)
    with pytest.raises(ValueError, match='ELF.*disjoint'):
        fit(plan)


def test_fixed_instruction_counts_cannot_hide_timing_gap(plan):
    spec = read_json(plan)
    spec['events'][0]['unit'] = 'instructions'
    write_json(plan, spec)
    result = fit(plan)
    assert result['status'] == 'inconclusive'
    assert result['training_scores']['synthetic'] > 0
    assert result['selected_errors'][spec['train'][0]][0]['role'] == 'consistency'
    assert result['headline']['metric'] == 'cycle_relative_error'
    assert result['headline']['benchmarks'][0]['cycle_gap_percent'] != 0


def test_constant_training_targets_are_inconclusive(plan):
    assert fit(plan)['status'] == 'inconclusive'
