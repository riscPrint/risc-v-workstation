#!/usr/bin/env python3
"""Publish reports from captured evidence under ROOT/.analysis/current.

Completed run directories are inputs. This command never rewrites them.
"""
import gzip
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory

from rvw.common.capture import Capture
from rvw.perf.analysis import analyze, render
from rvw.results.generation import publish
from captured import capture_run
from roi_observations import observe_captured


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def archive(item, path):
    data = item.copy.read_bytes()
    path.write_bytes(data if item.copy.suffix == '.gz' else gzip.compress(data, mtime=0))


def collect(root):
    root = Path(root)
    runs = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith('.'))
    with TemporaryDirectory(prefix='konata-collect-') as temporary:
        capture = Capture(Path(temporary) / 'inputs')
        # Prepare the entire batch before parsing a trace, running a tool or publishing.
        inputs = [(run.name, capture_run(capture, run, report=False))
                  for run in runs]
        env = capture.env('RISCV_OBJDUMP')
        objdump = capture.tool(env['RISCV_OBJDUMP'] or
            'riscv64-unknown-elf-objdump')
        record = capture.record()

        def build(directory):
            for name, item in inputs:
                out = directory / name
                out.mkdir()
                result = json.loads(item.result.copy.read_text())
                archive(item.trace, out / 'konata.log.gz')
                result['artifacts'] = {'konata': 'konata.log.gz'}
                result['elf'] = item.elf.resolved
                result['elf_sha256'] = item.elf.sha256
                # The manifest identifies derived output bytes. Keep old claims in the raw C1.
                result.pop('trace_sha256', None)
                result.pop('replay', None)
                report = analyze(item.perf(), isa='riscv', queue_stage='Iq', issue_stage='Is',
                                  head_stage='Iq', in_order_retirement=True, window=1000)
                report.update(capture=record, cache_key=None)
                roi = observe_captured(item, objdump, full=report)
                roi.update(capture=record, cache_key=None)
                result['source_result_sha256'] = item.result.sha256
                result['capture'] = record
                result['cache_key'] = None
                write(out / 'result.json', result)
                write(out / 'report.json', report)
                (out / 'report.txt').write_text(render(report) + '\n')
                write(out / 'roi-observations.json', roi)
            # Preserve the raw inputs in the immutable generation for later inspection.
            write(directory / 'capture.json', record)
            shutil.copytree(capture.root, directory / 'inputs')
            capture.verify_tools()

        identifier = publish(root / '.analysis', build)
        print(f'Published {identifier} under {root / ".analysis"}')
        return identifier


if __name__ == '__main__':
    collect(sys.argv[1])
