"""Execute generated C to check its initial-state uncertainty."""
import shutil
import subprocess

import pytest
from rvw.formal.bitc import translate

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('resettable', [False, True])
def test_unreset_state_starts_unknown(tmp_path, resettable):
    compiler = shutil.which('cc')
    if not compiler:
        pytest.skip('C compiler required for generated C execution')
    port = lambda direction, bits: dict(direction=direction, bits=bits)
    ports = dict(a=port('input', list(range(2, 10))), b=port('input', list(range(10, 18))),
                 clk=port('input', [18]), reset=port('input', [19]), start=port('input', [20]),
                 done=port('output', ['1']), y=port('output', [21] + ['0'] * 7))
    connections = dict(C=[18], D=[21], Q=[21])
    if resettable:
        connections['R'] = [19]
    design = {'modules': {'dut': dict(ports=ports, netnames={}, cells={
        'state': dict(type='$_DFF_PP0_' if resettable else '$_DFF_P_',
                      connections=connections)})}}
    code, _, put, _, unknown = translate(design, 8, 1, definedness=True)
    source = tmp_path / 'check.c'
    after_reset = 'tick(); return ' + (unknown('y') if resettable else '!' + unknown('y')) + ';'
    source.write_text(code + '\n_Bool nondet_bool(void) { return 0; }\n'
                      'int main(void) { init(); eval(); if (!' + unknown('y') + ') return 1;\n'
                      + '\n'.join(put('reset', '1')) + '\n' + after_reset + ' }\n')
    binary = tmp_path / 'check'
    subprocess.run([compiler, str(source), '-o', str(binary)], check=True, capture_output=True)
    assert subprocess.run([str(binary)], check=False).returncode == 0
