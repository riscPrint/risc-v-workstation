"""Bounded release scan. See rvw/README.md for coverage and limits."""
import json
import os
from pathlib import Path
import re
import subprocess

import pytest


REPO = Path(__file__).resolve().parents[2]
PERSONAL_PATH = re.compile(
    r"/(?:Users/|home/[^/\s\"'<>]+)|"
    r"[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]", re.I)
CREDENTIAL = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,}|"
    r"(?:AKIA|ASIA)[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{20,}|"
    r"sk_live_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{32,})\b|"
    r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----|"
    r"(?i:https?://[^\s/:]+:[^\s/@]+@)|"
    r"(?i:authorization\s*:\s*bearer\s+[A-Za-z0-9._~-]{16,})|"
    r'''(?i:["']?(?:password|passwd|api[_-]?key|access[_-]?token|secret[_-]?key|client[_-]?secret)["']?\s*[:=]\s*["']?[A-Za-z0-9_+/.~-]{12,})''')


def personal_path_lines(text):
    return [number for number, line in enumerate(text.splitlines(), 1)
            if PERSONAL_PATH.search(line)]


def scan_bytes(raw):
    # Preserve ASCII strings in binary and non-UTF-8 files. Also inspect UTF-16/32
    # text. This does not unpack archives or decode arbitrary secret encodings.
    texts = [raw.decode('latin-1')]
    # Every finding contains ASCII punctuation. Its UTF-16/32 encoding needs
    # zero octets. Without one, those decodings cannot add a finding.
    encodings = ('utf-8-sig', 'utf-16', 'utf-32') if b'\0' in raw else ('utf-8-sig',)
    for encoding in encodings:
        try:
            texts.append(raw.decode(encoding))
        except UnicodeError:
            pass
    found = set()
    for text in dict.fromkeys(texts):
        for number, line in enumerate(text.splitlines(), 1):
            if PERSONAL_PATH.search(line):
                found.add((number, 'personal_path'))
            if CREDENTIAL.search(line):
                found.add((number, 'credential'))
    return sorted(found)


def scan_tracked_tree(root):
    names = git_at(root, 'ls-files', '-z').split(b'\0')
    found = []
    for name in names:
        if not name:
            continue
        path = root / os.fsdecode(name)
        if path.is_symlink():
            raw = os.fsencode(os.readlink(path))
        elif path.is_file():
            raw = path.read_bytes()
        else:
            continue  # Deleted tracked files have no working-tree content.
        found.extend(f'{os.fsdecode(name)}:{line}:{rule}'
                     for line, rule in scan_bytes(raw))
    return found


def metadata_report(root):
    authors, committers, taggers, findings = set(), set(), set(), []
    # One git call for all commits; one `git show` per commit took minutes on large ref sets.
    records = git_at(root, 'log', '--all', '--format=%x1e%H%x00%an <%ae>%x00%cn <%ce>%x00%B')
    commits = []
    for record in records.split(b'\x1e')[1:]:
        oid, rest = record.split(b'\0', 1)
        commits.append(oid)
        fields = rest.split(b'\0', 2)
        authors.add(fields[0].decode('utf-8', errors='replace'))
        committers.add(fields[1].decode('utf-8', errors='replace'))
        for line, rule in scan_bytes(b'\n'.join(fields)):
            findings.append(dict(kind='commit', object=oid.decode(), line=line, rule=rule))
    tags = git_at(root, 'for-each-ref', '--format=%(objectname) %(objecttype)',
                  'refs/tags').splitlines()
    for tag in tags:
        oid, kind = tag.split()
        if kind != b'tag':
            continue  # Lightweight tags have no tagger or annotation.
        raw = git_at(root, 'cat-file', 'tag', oid.decode())
        for line in raw.split(b'\n\n', 1)[0].splitlines():
            if line.startswith(b'tagger '):
                taggers.add(line[7:].rsplit(b' ', 2)[0].decode('utf-8', errors='replace'))
        for line, rule in scan_bytes(raw):
            findings.append(dict(kind='tag', object=oid.decode(), line=line, rule=rule))
    return dict(authors=sorted(authors), committers=sorted(committers),
                taggers=sorted(taggers), commit_count=len(commits),
                tag_count=len(tags),
                shallow=git_at(root, 'rev-parse', '--is-shallow-repository').strip() == b'true',
                findings=findings)


def test_tracked_text_has_no_personal_paths():
    found = scan_tracked_tree(REPO)
    assert not found, 'Release hygiene findings (values omitted):\n' + '\n'.join(found)


def test_commit_and_tag_metadata():
    report = metadata_report(REPO)
    assert not report['findings'], report['findings']


@pytest.mark.parametrize('parent', ['Users', 'home'])
def test_path_check_finds_personal_directories(parent):
    text = 'neutral\n' + '/' + parent + '/developer/project\n'
    assert personal_path_lines(text) == [2]


def test_path_check_allows_neutral_examples():
    assert personal_path_lines('/work/core\n/path/to/core\n$RVW_HOME/rvw\n') == []


@pytest.mark.parametrize('script,args,variable', [
    ('SpinalChecks/boom/from-sim.sh', [], 'ENV_SH'),
    ('SpinalChecks/boom/run-suite.sh', [], 'ENV_SH'),
    ('SpinalChecks/boom/xprop.sh', [], 'ENV_SH'),
    ('rvw/examples/coverage/collect-boom.sh', ['out'], 'SPINAL_BOOM'),
])
def test_boom_helpers_name_missing_configuration(script, args, variable):
    env = dict(os.environ)
    env.pop(variable, None)
    result = subprocess.run(['bash', str(REPO / script), *args], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert variable in result.stderr


def test_suite_names_missing_test_directory(tmp_path):
    setup = tmp_path / 'env.sh'
    setup.write_text('')
    env = dict(os.environ, ENV_SH=str(setup))
    env.pop('RISCV_TESTS', None)
    result = subprocess.run(['bash', str(REPO / 'SpinalChecks/boom/run-suite.sh')],
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'RISCV_TESTS' in result.stderr


def test_wave_tools_use_path(tmp_path, monkeypatch):
    from rvw.wave.vcd import tool

    hidden = tmp_path / 'opt/oss-cad-suite/bin/fst2vcd'
    hidden.parent.mkdir(parents=True)
    hidden.write_text('#!/bin/sh\nexit 0\n')
    hidden.chmod(0o755)
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('PATH', '')
    assert tool('fst2vcd') is None
    monkeypatch.setenv('PATH', str(hidden.parent))
    assert tool('fst2vcd') == str(hidden)


@pytest.mark.parametrize('value', [
    'C:' + chr(92) + 'Users' + chr(92) + 'developer' + chr(92) + 'core',
    'D:' + '/Users' + '/developer/core',
    'C:' + chr(92) + 'Documents and Settings' + chr(92) + 'developer',
])
def test_windows_home_paths(value):
    assert personal_path_lines('neutral\n' + value) == [2]


def credential_samples():
    # Build synthetic values in parts so the repository scan does not flag fixtures.
    return [
        'gh' + 'p_' + 'A' * 36,
        'github_' + 'pat_' + 'a' * 82,
        'AK' + 'IA' + 'A' * 16,
        'ASI' + 'A' + 'B' * 16,
        'xox' + 'b-' + '1234567890-1234567890-' + 'a' * 24,
        'sk_' + 'live_' + 'a' * 24,
        'sk-' + 'a' * 48,
        'api_key=' + 'synthetic-secret-123456',
        '"password": "' + 'synthetic-secret-123456' + '"',
        'Authorization: Bearer ' + 'synthetic-secret-123456',
        'https://user:' + 'synthetic-secret-123456' + '@example.org',
        '-----BEGIN ' + 'RSA PRIVATE KEY-----',
        '-----BEGIN ' + 'OPENSSH PRIVATE KEY-----',
        '-----BEGIN ' + 'PRIVATE KEY-----',
        '-----BEGIN ' + 'ENCRYPTED PRIVATE KEY-----',
        '-----BEGIN ' + 'EC PRIVATE KEY-----',
        '-----BEGIN ' + 'PGP PRIVATE KEY BLOCK-----',
    ]


@pytest.mark.parametrize('value', credential_samples())
def test_credentials_are_detected_without_echoing_values(value):
    findings = scan_bytes(('neutral\n' + value).encode())
    assert findings == [(2, 'credential')]
    assert value not in repr(findings)


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16', 'utf-32', 'latin-1'])
def test_scan_includes_non_utf8_and_nul_bytes(encoding):
    value = 'caf\xe9\0\n' + credential_samples()[0]
    assert (2, 'credential') in scan_bytes(value.encode(encoding))


def test_scan_allows_placeholders():
    assert scan_bytes(b'password = "${PASSWORD}"\napi_key = "example"\n') == []


def git_at(root, *args, env=None):
    return subprocess.run(['git', *args], cwd=root, env=env, check=True,
                          capture_output=True).stdout


def test_tracked_scan_checks_symlink_targets_and_binary_files(tmp_path):
    git_at(tmp_path, 'init', '-q')
    (tmp_path / 'link').symlink_to('/' + 'home/developer/missing')
    (tmp_path / 'blob').write_bytes(b'\xff\0\n' + credential_samples()[0].encode())
    git_at(tmp_path, 'add', '.')
    assert scan_tracked_tree(tmp_path) == [
        'blob:2:credential', 'link:1:personal_path',
    ]


def test_metadata_reports_identities_separately(tmp_path):
    git_at(tmp_path, 'init', '-q')
    env = dict(os.environ, GIT_AUTHOR_NAME='Synthetic Owner',
               GIT_AUTHOR_EMAIL='owner@example.org',
               GIT_COMMITTER_NAME='Synthetic Committer',
               GIT_COMMITTER_EMAIL='committer@example.org')
    git_at(tmp_path, 'commit', '--allow-empty', '-m', credential_samples()[0], env=env)
    git_at(tmp_path, 'tag', '-a', 'release-test', '-m', credential_samples()[1], env=env)
    git_at(tmp_path, 'tag', 'lightweight', env=env)
    report = metadata_report(tmp_path)
    assert report['authors'] == ['Synthetic Owner <owner@example.org>']
    assert report['committers'] == ['Synthetic Committer <committer@example.org>']
    assert report['taggers'] == ['Synthetic Committer <committer@example.org>']
    assert report['commit_count'] == 1
    assert report['tag_count'] == 2
    assert {row['kind'] for row in report['findings']} == {'commit', 'tag'}
    assert all(row['rule'] == 'credential' for row in report['findings'])
    assert credential_samples()[0] not in str(report)


def test_metadata_identity_alone_does_not_fail(tmp_path):
    git_at(tmp_path, 'init', '-q')
    env = dict(os.environ, GIT_AUTHOR_NAME='Synthetic Owner',
               GIT_AUTHOR_EMAIL='owner@example.org',
               GIT_COMMITTER_NAME='Synthetic Owner',
               GIT_COMMITTER_EMAIL='owner@example.org')
    git_at(tmp_path, 'commit', '--allow-empty', '-m', 'neutral', env=env)
    assert metadata_report(tmp_path)['findings'] == []


def test_release_docs_use_public_setup_and_provenance():
    for name in ('rvw/README.md', 'rvw/tests/data/regen.sh',
                 'SpinalWaves/README.md', 'SpinalTrace/README.md'):
        assert 'spinal-boom/env.sh' not in (REPO / name).read_text()
    for name, stale in (
        ('README.md', 'Git history retains'),
        ('README.md', 'their full histories were merged'),
        ('ROADMAP.md', 'Git history retains'),
        ('SpinalWaves/docs/RUST_PORTING.md', '<pristine commit>'),
        ('SpinalTrace/PORTING_NOTES.md', 'imported verbatim in the first commit'),
        ('SpinalWaves/UPSTREAM_WATCH.md', 'scheduled-task:'),
    ):
        assert stale not in (REPO / name).read_text()
    readme = (REPO / 'README.md').read_text()
    assert 'private' in readme.split('## Quickstart')[0]
    assert 'examples/vexriscv' in readme.split('## Quickstart')[0]


if __name__ == "__main__":
    print(json.dumps(metadata_report(REPO), indent=2))


@pytest.mark.parametrize('encoding', ['ascii', 'utf-8-sig', 'utf-16', 'utf-32'])
def test_scan_keeps_findings_across_text_encodings(encoding):
    # Split sensitive-looking strings so the repository scan does not flag this fixture.
    text = 'neutral\n' + '/' + 'Users' + '/tester/file\n' + 'gh' + 'p_' + 'a' * 40
    findings = scan_bytes(text.encode(encoding))
    assert (2, 'personal_path') in findings
    assert (3, 'credential') in findings


def test_scan_non_utf8_binary_keeps_ascii_findings():
    raw = b'\xff\xfe\xff\n' + b'/' + b'home' + b'/tester/file'
    assert (2, 'personal_path') in scan_bytes(raw)
