#!/usr/bin/env python3
"""Build a local MkDocs site from tracked Markdown without changing the sources."""
import argparse
import os
from pathlib import Path
import shutil
import re
from urllib.parse import quote
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def readmes():
    paths = set()
    for directory, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('target', 'node_modules', 'simWorkspace', 'out')]
        if 'README.md' in files:
            paths.add(Path(directory) / 'README.md')
    return sorted(p.relative_to(ROOT).as_posix() for p in paths
                  if not any(part.startswith('.') for part in p.relative_to(ROOT).parts))


def tracked_readmes(names):
    return [name for name in readmes() if name in names]


def navigation(nav, names):
    """Keep curated order and add all remaining tracked Markdown pages."""
    def targets(items):
        for item in items:
            if isinstance(item, str):
                yield item
            elif isinstance(item, dict):
                yield from targets(item.values())
            elif isinstance(item, (list, tuple)):
                yield from targets(item)
    known = set(targets(nav))
    extra = sorted(name for name in names if name.endswith('.md') and name not in known)
    return [*nav, {'More documentation': [{name: name} for name in extra]}]


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args()
    # Every tool gets its own source README page. Copy all Markdown for local links.
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    pages = tracked_readmes(names)
    revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    with tempfile.TemporaryDirectory(prefix='rvw-docs-') as temporary:
        stage=(Path(temporary)/'source').resolve();stage.mkdir()
        for name in names:
            source=ROOT/name
            if not name or not source.is_file() or source.is_symlink():continue
            if source.suffix.lower() not in ('.md','.png','.svg','.jpg','.gif'):continue
            target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        # Source-code links belong in the repository viewer, not the HTML payload.
        for page in stage.rglob('*.md'):
            def source_link(match):
                target=match[1]
                if '://' in target or target.startswith(('#','mailto:')):
                    return match[0]
                candidate=(page.parent/target.split('#',1)[0]).resolve()
                if not candidate.is_relative_to(stage) or candidate.exists():
                    return match[0]
                source=ROOT/candidate.relative_to(stage)
                if source.is_file():
                    url='https://github.com/riscPrint/risc-v-workstation/blob/'+revision+'/'+quote(source.relative_to(ROOT).as_posix())
                    return ']('+url+')'
                return match[0]
            page.write_text(re.sub(r'\]\(([^\s)]+)\)',source_link,page.read_text()))
        if a.check:
            assert all((stage/name).is_file() for name in pages)
            print(f'{len(pages)} tool README pages; local staging check only')
            return
        from mkdocs.config import load_config
        from mkdocs.commands.build import build
        config=load_config(str(ROOT/'mkdocs.yml'),docs_dir=str(stage),site_dir=str(a.out.resolve()))
        config.nav = navigation(config.nav or [], [p.relative_to(stage).as_posix() for p in stage.rglob('*.md')])
        build(config)
if __name__=='__main__':main()
