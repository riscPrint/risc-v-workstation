import importlib.util
from pathlib import Path
import subprocess
import pytest

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('release_scan_cli',ROOT/'scripts/scan-release.py')
scanner=importlib.util.module_from_spec(spec);spec.loader.exec_module(scanner)


def test_release_report_redacts_secrets_and_counts_identities(tmp_path):
    import os
    env={**os.environ,'GIT_AUTHOR_NAME':'Fixture','GIT_AUTHOR_EMAIL':'fixture@example.org',
         'GIT_COMMITTER_NAME':'Fixture','GIT_COMMITTER_EMAIL':'fixture@example.org'}
    def git(*args):
        subprocess.run(['git','-C',str(tmp_path),*args],check=True,env=env,capture_output=True)
    git('init','-q')
    token='ghp_'+'a'*36
    (tmp_path/'bad.txt').write_text(token+'\n'+'/'+'Users/example/private\n')
    git('add','.');git('commit','-qm','fixture')
    report=scanner.scan(tmp_path,since='2000-01-01')
    from datetime import datetime, timezone
    today = scanner.scan(tmp_path, since=datetime.now(timezone.utc).date().isoformat())
    assert today['changed_file_count'] == 1
    assert token not in str(report)
    assert report['changed_personal_paths']==['bad.txt:2:personal_path']
    assert len(report['tracked_findings'])==2
    assert report['identity_counts']['authors']==1
    assert 'not inferred' in report['publication_approval']
