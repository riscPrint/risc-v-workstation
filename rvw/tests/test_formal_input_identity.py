"""Committed bytes are provenance evidence, not adapter conformance or proof."""
import hashlib
import subprocess

from rvw.formal.input_identity import committed_inputs


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def test_committed_modified_untracked_and_copied_bytes(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.email', 'fixture@example.com')
    git(tmp_path, 'config', 'user.name', 'Fixture')
    tracked = tmp_path / 'design.v'
    tracked.write_text('module dut; endmodule\n')
    digest = hashlib.sha256(tracked.read_bytes()).hexdigest()
    git(tmp_path, 'add', 'design.v')
    git(tmp_path, 'commit', '-qm', 'fixture')
    result = committed_inputs({str(tracked): digest})
    assert result['all_committed']
    assert result['files'][0]['revision'] == git(tmp_path, 'rev-parse', 'HEAD')
    tracked.write_text('module changed; endmodule\n')
    # The captured bytes, rather than a later worktree read, determine identity.
    assert committed_inputs({str(tracked): digest})['all_committed']
    result = committed_inputs({str(tracked): hashlib.sha256(tracked.read_bytes()).hexdigest()})
    assert not result['all_committed'] and result['files'][0]['status'] == 'modified'
    result = committed_inputs({str(tmp_path / 'generated.v'): digest})
    assert not result['all_committed'] and result['files'][0]['status'] == 'untracked_or_unavailable'


def test_no_repository(tmp_path):
    assert not committed_inputs({str(tmp_path / 'rtl'): 'a' * 64})['all_committed']
    assert not committed_inputs({})['all_committed']
