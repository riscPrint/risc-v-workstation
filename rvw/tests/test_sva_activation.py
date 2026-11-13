
import pytest

from rvw.common.capture import Capture
from rvw.formal.antecedent_cover import prepare
from rvw.formal.event_sim import counts
from rvw.formal.temporal import lower

pytestmark = pytest.mark.fast


def test_source_marker_and_antecedent_survive_lowering():
    model, properties = lower('module Top(input clk, req, ack);\n'
                              'response: assert property (@(posedge clk) req |=> ack); '
                              '// rvw-source: Core.scala:42\nendmodule', simulation=True)
    assert properties[0]['source'] == dict(file='Core.scala', line=42)
    assert properties[0]['antecedent'] == 'req'
    assert 'RVW_ACTIVATE rvw_sva_0_0' in model
    assert 'rvw_sva_0_0_antecedent' in model
    result = counts('RVW_SVA rvw_sva_0_0 assert pass\n'
                    'RVW_ACTIVATE rvw_sva_0_0\nRVW_ACTIVATE rvw_sva_0_0\n', properties)
    assert result[0]['activated'] == 2
    assert result[0]['source']['line'] == 42
    assert result[0]['passed'] == 1


def test_false_antecedent_is_not_activation():
    _, properties = lower('module Top(input clk); '
                          'p: assert property (@(posedge clk) 0 |=> 0); endmodule', simulation=True)
    result = counts('RVW_SVA rvw_sva_0_0 assert pass\n', properties)
    assert result[0]['passed'] == 1
    assert result[0]['activated'] == 0


def test_cover_preparation_captures_separate_input(tmp_path):
    (tmp_path / 'model.sv').write_text('module Top(input clk); always @(posedge clk) cover(1); endmodule')
    (tmp_path / 'cover.sby').write_text('[options]\nmode cover\ndepth 8\n[engines]\nsmtbmc yices\n'
                                       '[script]\nread_verilog -formal model.sv\nprep -top Top\n[files]\nmodel.sv\n')
    directory = tmp_path / 'out'
    directory.mkdir()
    job, engine, depth = prepare(dict(activation_sby='cover.sby'), tmp_path / 'suite.toml',
                                 Capture(directory / 'inputs'), directory)
    assert 'mode cover' in job.read_text()
    assert engine == 'smtbmc:yices'
    assert depth == 8
    assert str(tmp_path / 'model.sv') not in job.read_text()


def test_activation_needs_cover_mode(tmp_path):
    (tmp_path / 'bad.sby').write_text('[options]\nmode prove\n')
    out = tmp_path / 'out'
    out.mkdir()
    with pytest.raises(ValueError, match='activation_requires_cover_mode'):
        prepare(dict(activation_sby='bad.sby'), tmp_path / 'suite.toml', Capture(out / 'inputs'), out)
