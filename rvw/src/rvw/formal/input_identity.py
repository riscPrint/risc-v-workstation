"""Bind copied formal input bytes to Git commits without asserting RTL origin."""
import hashlib
from pathlib import Path

from rvw.common.capture import run_git


def committed_inputs(snapshots):
    rows = []
    locations = {}
    revisions = {}
    for name, copied_sha256 in sorted(snapshots.items()):
        path = Path(name).resolve()
        row = dict(path=name, sha256=copied_sha256, status='unavailable')
        try:
            parent = str(path.parent)
            if parent not in locations:
                r = run_git(path.parent, 'rev-parse', '--show-toplevel')
                locations[parent] = Path(r.stdout.strip()) if r.returncode == 0 and not r.timed_out else None
            repo = locations[parent]
            if repo is not None:
                if repo not in revisions:
                    r = run_git(repo, 'rev-parse', 'HEAD')
                    revisions[repo] = r.stdout.strip() if r.returncode == 0 and not r.timed_out else None
                rev = revisions[repo]
                if rev:
                    relative = path.relative_to(repo).as_posix()
                    r = run_git(repo, 'show', f'{rev}:{relative}', text=False)
                    row.update(repository=str(repo), revision=rev, relative_path=relative)
                    if r.returncode == 0 and not r.timed_out:
                        row['status'] = ('committed' if hashlib.sha256(r.stdout).hexdigest() == copied_sha256
                                         else 'modified')
                    else:
                        row['status'] = 'untracked_or_unavailable'
        except (OSError, ValueError):
            pass
        rows.append(row)
    return dict(files=rows, all_committed=bool(rows) and all(r['status'] == 'committed' for r in rows))
