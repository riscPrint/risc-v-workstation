"""Real-core property preparation and exact observation-cache boundaries."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from rvw.formal import regression_cache

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


def example(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'examples/vexriscv/rvw' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_counts_replace_every_display():
    model, props = example('core-properties-sim').instrument(
        'module VexTop(input clk, reset, req, ack);\nendmodule',
        'response: assert property (@(posedge clk) disable iff(reset) req |=> ack);\n'
        'active: cover property (@(posedge clk) req);')
    assert len(props) == 2
    assert 'RVW_SVA' not in model
    assert 'final $display("RVW_COUNT' in model
    assert 'rvw_sva_0_0_pass <= rvw_sva_0_0_pass + 1' in model


def test_prepare_keeps_core_preprocessor_and_checks_separate(tmp_path):
    rtl = tmp_path / 'rtl'
    rtl.mkdir()
    (rtl / 'VexTop.v').write_text('module VexTop(input clk,reset,a);\n`ifdef SYNTHESIS\n`endif\nendmodule')
    (rtl / 'properties.sv').write_text('a: assert property (@(posedge clk) a);\n'
                                       'c: cover property (@(posedge clk) a);\n')
    inventory = example('core-properties').prepare(rtl, tmp_path / 'jobs')
    assert [p['id'] for p in inventory] == ['a']
    assert '`ifdef SYNTHESIS' in (tmp_path / 'jobs/a/model.sv').read_text()
    assert 'mode bmc' in (tmp_path / 'jobs/a/job.sby').read_text()


def cache_input(tmp_path, text='module Top; endmodule'):
    source = tmp_path / 'model.sv'
    source.write_text(text)
    job = tmp_path / 'job.sby'
    job.write_text('[options]\nmode bmc\ndepth 12\n[engines]\nsmtbmc yices\n'
                   '[script]\nread_verilog -formal -sv model.sv\nprep -top Top\n'
                   f'[files]\nmodel.sv {source}\n')
    tools = SimpleNamespace(checks=[], env={'PATH': str(tmp_path / 'tools') + ':/bin'}, directory=tmp_path / 'tools')
    return job, tools


def test_cache_key_tracks_source_depth_and_tool_environment(tmp_path):
    job, tools = cache_input(tmp_path)
    original = regression_cache.identity(job, tools)
    (tmp_path / 'model.sv').write_text('module Top; wire fault; endmodule')
    assert regression_cache.identity(job, tools) != original
    (tmp_path / 'model.sv').write_text('module Top; endmodule')
    job.write_text(job.read_text().replace('depth 12', 'depth 13'))
    assert regression_cache.identity(job, tools) != original
    job.write_text(job.read_text().replace('depth 13', 'depth 12'))
    tools.env['PATH'] += ':/changed'
    assert regression_cache.identity(job, tools) != original


@pytest.mark.parametrize('text', ['`include "external.sv"', '$readmemh("external.hex", mem);'])
def test_cache_refuses_unclosed_sources(tmp_path, text):
    job, tools = cache_input(tmp_path, text)
    assert regression_cache.identity(job, tools) is None


def test_cache_restores_only_intact_conditional_pass(tmp_path):
    source = tmp_path / 'run'
    (source / 'sby/model').mkdir(parents=True)
    (source / 'sby/model/design_prep.il').write_text('assert cell')
    (source / 'sby/logfile.txt').write_text('PASS')
    (source / 'run.log').write_text('PASS')
    value = dict(test='exact')
    result = dict(formal_status='bounded-pass', activation='not_measured')
    cache = tmp_path / 'cache'
    regression_cache.publish(cache, value, source, result)
    target = tmp_path / 'restored'
    target.mkdir()
    assert regression_cache.restore(cache, value, target) == result
    entry = cache / regression_cache.key_for(value)
    (entry / 'sby/model/design_prep.il').write_text('changed')
    assert regression_cache.restore(cache, value, tmp_path / 'tampered') is None


def test_cache_does_not_publish_failure(tmp_path):
    regression_cache.publish(tmp_path / 'cache', {}, tmp_path, dict(formal_status='failed'))
    assert not (tmp_path / 'cache').exists()
