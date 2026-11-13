"""Pinned CIRCT binaries outside the repository. No source build or fallback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import tarfile
from rvw.common.proc import run_group

VERSION='firtool-1.163.0'
RELEASES={
 ('Darwin','arm64'):('macos-arm64','820ad2bb75605ab81ff1b584e04726fdf4e5c21a8f7f910df0b8fa36e9d4b760'),
 ('Darwin','x86_64'):('macos-x64','3883ffbade01d185e47272551887c4b48fc080aafac9c8faa4034e41f04bec16'),
 ('Linux','x86_64'):('linux-x64','2a3b8a19a8884e7adf9508555346bb9107feb6aaced9ad7fdf247dbf7048a945')}


def main():
 p=argparse.ArgumentParser(__doc__)
 p.add_argument('--check',action='store_true');p.add_argument('--dry-run',action='store_true')
 args=p.parse_args()
 key=(platform.system(),platform.machine())
 if key not in RELEASES:raise SystemExit('unsupported CIRCT release host: '+repr(key))
 host,digest=RELEASES[key]
 root=Path(os.environ.get('RVW_CIRCT',Path.home()/'.cache/rvw/circt'/VERSION)).expanduser().resolve()
 if root.is_relative_to(Path(__file__).resolve().parents[4]):raise SystemExit('CIRCT install must be outside the repository')
 print(json.dumps(dict(version=VERSION,root=str(root),sha256=digest)))
 if args.dry_run:return
 if not args.check and not (root/'bin/arcilator').exists():
  root.parent.mkdir(parents=True,exist_ok=True)
  archive=root.parent/(VERSION+'-'+host+'.tar.gz')
  url=f'https://github.com/llvm/circt/releases/download/{VERSION}/circt-full-shared-{host}.tar.gz'
  result=run_group(['curl','-fL','--max-time','180',url,'-o',str(archive)],timeout=190,capture=True)
  if result.returncode or result.timed_out:raise SystemExit('CIRCT download failed: '+result.stderr[-500:])
  if hashlib.sha256(archive.read_bytes()).hexdigest()!=digest:raise SystemExit('CIRCT archive digest differs')
  # The pinned archive contains one versioned directory. Refuse an existing install.
  with tarfile.open(archive) as tar:tar.extractall(root.parent,filter='data')
  installed=root.parent/VERSION
  if installed!=root:installed.rename(root)
 for name in ('circt-verilog','arcilator','llc'):
  executable=root/'bin'/name
  if not executable.is_file():raise SystemExit('missing native CIRCT tool: '+str(executable))
  result=run_group([str(executable),'--version'],timeout=30,capture=True)
  if result.returncode:raise SystemExit('CIRCT tool failed: '+name)
  if name=='circt-verilog' and VERSION not in result.stdout+result.stderr:
   raise SystemExit('CIRCT release version differs')
 print('Set RVW_CIRCT='+str(root))

if __name__=='__main__':main()
