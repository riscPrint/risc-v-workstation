"""Make a private Git snapshot of pinned VexiiRiscv and dependency sources."""
import argparse
import json
from pathlib import Path
import shutil
from rvw.common.proc import run_group


def git(root,*args,binary=False):
    r=run_group(['git','-C',str(root),*args],capture=True,text=not binary,timeout=30)
    if r.returncode:raise RuntimeError(r.stderr)
    return r.stdout


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--revision',required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();source=a.source.resolve();out=a.out.resolve()
    if git(source,'rev-parse','HEAD').strip()!=a.revision:raise ValueError('core revision differs')
    out.mkdir(parents=True,exist_ok=False);pins={}
    for relative in ('','ext/SpinalHDL','ext/rvls'):
        repo=source/relative;revision=git(repo,'rev-parse','HEAD').strip()
        if git(repo,'diff','HEAD','--ignore-submodules=all'):raise ValueError('tracked source changes: '+relative)
        if relative:
            recorded=git(source,'ls-tree','HEAD',relative).split()[2]
            if recorded!=revision:raise ValueError('dependency revision differs: '+relative)
        count=0
        for raw in git(repo,'ls-files','-z','--cached',binary=True).split(b'\0'):
            if not raw:continue
            path=Path(raw.decode());origin=repo/path
            if origin.is_dir():continue  # Gitlinks are copied explicitly above.
            target=out/relative/path;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(origin,target);count+=1
        pins[relative or '.']=dict(revision=revision,files=count)
    (out/'rvw-source-pins.json').write_text(json.dumps(dict(schema='rvw.source-pins/1',components=pins),indent=2)+'\n')
    git(out,'init','-b','snapshot')
    git(out,'add','-f','.')
    git(out,'-c','user.name=rvw source snapshot','-c','user.email=rvw@localhost',
        'commit','-qm','chore(sim): snapshot pinned core and dependency sources')
    print(json.dumps(dict(snapshot_revision=git(out,'rev-parse','HEAD').strip(),components=pins)))

if __name__=='__main__':main()
