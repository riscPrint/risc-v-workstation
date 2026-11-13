#!/usr/bin/env python3
"""Create committed gate controls without changing the worktree or real index."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
repo = Path(subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], text=True).strip())
out = root / 'rvw/out'
out.mkdir(parents=True, exist_ok=True)
environment = os.environ | {'GIT_INDEX_FILE': str(out / 'gate-control-index')}


def git(*args, input=None):
    return subprocess.check_output(['git', '-C', str(repo), *args], env=environment, input=input).decode().strip()


good = git('rev-parse', 'HEAD')
tree = git('rev-parse', 'HEAD^{tree}')
path = (root / 'src/main/scala/ooomini/MulDiv.scala').relative_to(repo).as_posix()
source = git('show', f'{good}:{path}')
needle = 'product := uu(31 downto 0).asBits'
if source.count(needle) != 1:
    raise SystemExit('Expected exactly one low-product assignment')
blob = git('hash-object', '-w', '--stdin', input=source.replace(needle, needle + ' ^ B(1,32 bits)').encode())
git('read-tree', good)
git('update-index', '--cacheinfo', f'100644,{blob},{path}')
bug = git('commit-tree', git('write-tree'), '-p', good, input=b'test(ooo-mini): plant multiplier low-bit fault\n')
fix = git('commit-tree', tree, '-p', bug, input=b'fix(ooo-mini): restore correct multiply result\n')
revisions = dict(good=good, bug=bug, fix=fix)
for name, revision in revisions.items():
    git('update-ref', f'refs/rvw/ooo-mini-mem/{name}', revision)
(out / 'gate-revisions.json').write_text(json.dumps(revisions, indent=2) + '\n')
print(json.dumps(revisions))
