"""ELF symbols joined with wave PC values: annotations and a per-function edge profile."""
import json
import subprocess
import sys
from pathlib import Path

from rvw.wave import ops, symbols

ELF = str(Path(__file__).parent / 'data' / 'wave_profile.elf')   # _start 0x80000000+12, work 0x8000000c+12


def wave(tmp_path):
    body = ['$timescale 1ns $end', '$scope module TOP $end', '$var wire 1 ! clk $end',
            '$var wire 1 " commit_valid $end', '$var wire 64 # commit_pc [63:0] $end',
            '$upscope $end', '$enddefinitions $end', '#0', '$dumpvars', '0!', '1"', 'b' + bin(0x80000000)[2:] + ' #', '$end']
    pcs = {5: 0x80000004, 15: 0x8000000c, 25: 0x80000010, 35: 0x8000000c, 55: 0x90000000}
    for t in range(5, 75, 5):
        rising = (t // 5) % 2 == 1
        body.append(f'#{t}')
        body.append(('1' if rising else '0') + '!')
        if t in pcs:
            body.append('b' + bin(pcs[t])[2:] + ' #')
        if t == 45:
            body.append('0"')
        if t == 55:
            body.append('1"')
    p = tmp_path / 'w.vcd'
    p.write_text('\n'.join(body) + '\n')
    return str(p)


def test_lookup():
    s = symbols.Symbols(ELF)
    assert s.lookup(0x80000004) == {'symbol': '_start', 'offset': 4}
    assert s.lookup(0x80000010)['symbol'] == 'work'
    assert s.lookup(0x80000018) is None and s.lookup(0x10) is None


def test_profile_and_annotations(tmp_path):
    w = wave(tmp_path)
    r = symbols.profile(w, 'commit_pc', ELF, valid='commit_valid')
    assert r['edges'] == 6 and r['unknown'] == 0
    assert {f['function']: f['edges'] for f in r['functions']} == {'work': 3, '_start': 2, '(no symbol)': 1}
    assert [(p['function'], p['start'], p['end']) for p in r['phases']] == [
        ('_start', 5, 15), ('work', 25, 45), ('(no symbol)', 65, 65)]
    page = symbols.annotate_changes(ops.changes_page(w, 'commit_pc'), ELF)
    assert [c.get('symbol') for c in page['changes']][:3] == ['_start+0x0', '_start+0x4', 'work+0x0']
    assert 'symbol' not in page['changes'][-1]
    out = subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'profile', w, 'commit_pc', '--elf', ELF,
                          '--valid', 'commit_valid', '--json'], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)['functions'][0] == {'function': 'work', 'edges': 3, 'fraction': 0.5}
    out = subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'changes', w, 'commit_pc', '--elf', ELF],
                         capture_output=True, text=True)
    assert 'work+0x4' in out.stdout
