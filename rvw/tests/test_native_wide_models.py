"""Native packed ports across storage boundaries, with public-port VCD."""
import os
from pathlib import Path
import random
import shutil

import pytest
from rvw.sim.native_models import Model


def test_wide_ports_and_waves_on_both_engines(tmp_path):
    circt = os.environ.get('RVW_CIRCT')
    if not circt or not (Path(circt) / 'bin/arcilator').is_file():
        pytest.skip('pinned CIRCT required')
    if not shutil.which('verilator'):
        pytest.skip('Verilator required')
    widths = [31, 32, 63, 64, 65, 129, 257]
    ports = dict(clk=('input', 1), reset=('input', 1))
    declarations = ['input clk, reset']
    logic = []
    for w in widths:
        ports[f'd{w}'] = ('input', w)
        ports[f'q{w}'] = ('output', w)
        declarations += [f'input [{w-1}:0] d{w}', f'output reg [{w-1}:0] q{w}']
        logic += [f'always @(posedge clk) if(reset) q{w} <= 0; else q{w} <= q{w} + d{w};']
    rtl = tmp_path / 'wide.sv'
    rtl.write_text('module Wide(' + ','.join(declarations) + ');\n' + '\n'.join(logic) + '\nendmodule\n')
    sequences = []
    for backend in ('arcilator', 'verilator'):
        wave = tmp_path / (backend + '.vcd')
        model = Model(backend, [rtl], 'Wide', ports, tmp_path / backend, circt=circt, wave=wave)
        try:
            for name, (direction, _) in ports.items():
                if direction == 'input':
                    model.write(name, int(name == 'reset'))
            model.eval(); model.write('clk', 1); model.eval()
            model.write('clk', 0); model.eval(); model.write('reset', 0)
            expected = {w: 0 for w in widths}
            rng = random.Random(71)
            observed = []
            for _ in range(20):
                for w in widths:
                    value = rng.getrandbits(w)
                    model.write(f'd{w}', value)
                    expected[w] = (expected[w] + value) % (1 << w)
                model.eval(); model.write('clk', 1); model.eval()
                model.write('clk', 0); model.eval()
                result = [model.read(f'q{w}') for w in widths]
                assert result == [expected[w] for w in widths]
                observed.append(result)
            with pytest.raises(ValueError):
                model.write('d129', 1 << 129)
            sequences.append(observed)
        finally:
            model.close()
        text = wave.read_text()
        assert '$var wire 257' in text
        assert f'{expected[257]:0257b}' in text
    assert sequences[0] == sequences[1]
    assert (tmp_path / 'arcilator.vcd').read_bytes() == (tmp_path / 'verilator.vcd').read_bytes()
