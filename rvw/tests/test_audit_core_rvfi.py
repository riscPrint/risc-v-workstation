"""Structured C1 monitor codes must survive C3 publication and comparison."""
from pathlib import Path

from rvw.regress.cli import execute_json


def test_gate_rejects_changed_structured_monitor_code(fake):
    original = Path(__file__).with_name('fake_adapter.py')
    adapter = fake.root / 'coded_adapter.py'
    adapter.write_text(original.read_text().replace(
        '    if metrics:\n',
        '    if "monitor_code" in d:\n'
        '        res["details"] = {"rvfi_errcode": int(d["monitor_code"])}\n'
        '    if metrics:\n'))
    fake.config.write_text(fake.config.read_text().replace(str(original), str(adapter)))
    base = fake.commit({'rv64ui-p-add': 'status=rvfi_error message=RVFI_violation monitor_code=105'}, 'first')
    cand = fake.commit({'rv64ui-p-add': 'status=rvfi_error message=RVFI_violation monitor_code=106'}, 'second')
    verdict = execute_json('gate', core=str(fake.config), base_rev=base, cand_rev=cand,
                           no_cache=True)
    assert verdict['verdict'] == 'reject'
    assert verdict['new_failures'][0]['signature'] == 'rvfi_error:106'
    assert not verdict['still_failing']
