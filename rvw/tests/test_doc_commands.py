"""Check executable examples with argparse, without invoking their handlers."""
import importlib.util
from pathlib import Path
import pytest
from rvw.cli import build_parser

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('doc_commands', ROOT / 'scripts/check-doc-commands.py')
docs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs)


def test_documented_commands_parse():
    parser = build_parser()
    records = [record for path in docs.documents() for record in docs.extract(path)]
    assert len(records) > 1000
    errors = [f"{r['file']}:{r['line']}: {error}" for r in records if (error := docs.validate(r, parser))]
    assert not errors, '\n'.join(errors)


def test_extraction_tracks_lines_and_shell_segments(tmp_path):
    path = tmp_path / 'README.md'
    path.write_text('```sh\ncp -R rvw dest\nrvw regress list; rvw query info --json\n```\n`rvw doctor --bogus`\n')
    original = docs.ROOT
    docs.ROOT = tmp_path
    try:
        records = list(docs.extract(path))
    finally:
        docs.ROOT = original
    assert [r['line'] for r in records] == [3, 3, 5]
    assert [r['argv'][1] for r in records] == ['regress', 'query', 'doctor']
    parser = build_parser()
    assert docs.validate(records[-1], parser) == 'unknown option: --bogus'


def test_required_arguments_and_types_are_checked():
    parser = build_parser()
    record = dict(kind='command', argv=['rvw', 'cosim', 'check', '--trace', 'trace'])
    assert docs.validate(record, parser)
    record['argv'] = ['rvw', 'doctor', '--bogus']
    assert docs.validate(record, parser)
    record['argv'] = ['rvw', 'debug', 'suite', '--list']
    assert docs.validate(record, parser) is None


def test_referenced_shell_scripts_have_valid_syntax():
    import subprocess
    scripts = set()
    for path in docs.documents():
        for record in docs.extract(path):
            name = record['argv'][0]
            if name.startswith(('scripts/', 'RiscvSim/')) and name.endswith('.sh'):
                candidates = (ROOT / name, path.parent / name)
                script = next((p for p in candidates if p.is_file()), None)
                assert script is not None, f"{record['file']}:{record['line']}: missing {name}"
                scripts.add(script)
    assert scripts
    for script in sorted(scripts):
        done = subprocess.run(['bash', '-n', str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
