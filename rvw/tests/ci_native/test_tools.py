"""Tiny native CI fixtures. No core checkout or Scala build."""
import subprocess
import pytest

from rvw.doctor.inventory import report
PRESENT = {r['name'] for r in report() if r['status'] == 'installed'}

def needs(*tools):
    def decorate(test):
        test = pytest.mark.native_light(*tools)(test)
        return pytest.mark.skipif(bool(set(tools) - PRESENT), reason='CI inventory missing: ' + ', '.join(sorted(set(tools) - PRESENT)))(test)
    return decorate

pytestmark = pytest.mark.native_light


def run(command, directory):
    result = subprocess.run(command, cwd=directory, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@needs('Verilator')
def test_verilator_tiny_lint(tmp_path):
    (tmp_path / 'tiny.v').write_text('module tiny(input a, output y); assign y = a; endmodule\n')
    run(['verilator', '--lint-only', 'tiny.v'], tmp_path)


@needs('Yosys')
def test_yosys_tiny_equivalence(tmp_path):
    (tmp_path / 'tiny.v').write_text('module tiny(input a, output y); assign y = a ^ a; endmodule\n')
    run(['yosys', '-Q', '-T', '-p', 'read_verilog tiny.v; prep -top tiny; sat -prove y 0 -verify'], tmp_path)


@needs('SymbiYosys', 'Yosys', 'Z3')
def test_sby_tiny_assertion(tmp_path):
    (tmp_path / 'tiny.sv').write_text('module tiny(input a); always @* assert ((a | ~a) == 1\'b1); endmodule\n')
    (tmp_path / 'tiny.sby').write_text('[options]\nmode prove\ndepth 1\n[engines]\nsmtbmc z3\n[script]\nread -formal tiny.sv\nprep -top tiny\n[files]\ntiny.sv\n')
    run(['sby', '-f', 'tiny.sby'], tmp_path)


@needs('Spike')
def test_spike_tiny_disassembly(tmp_path):
    # Spike's companion disassembler reads a single ADDI instruction.
    from shutil import which
    if not which('spike-dasm'):
        pytest.skip('Spike companion spike-dasm is absent')
    result = subprocess.run(['spike-dasm'], input='DASM(00000013)\n', text=True, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert 'nop' in result.stdout or 'addi' in result.stdout
