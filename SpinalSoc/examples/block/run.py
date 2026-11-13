#!/usr/bin/env python3
"""Generate a fresh block composition and run its directed native test."""
from pathlib import Path
import argparse
from rvw.common.proc import run_group
from rvw.soc.compose import compose

parser = argparse.ArgumentParser()
parser.add_argument('--out', required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
here = Path(__file__).resolve().parent
out = Path(args.out).resolve()
compose(here/'compose.json', out)
source = out/'ComposedSoc.scala'
source.write_text(source.read_text().replace('package generated','package blockgenerated'))
# JSON string syntax also quotes these ordinary paths in Scala settings.
import json
settings = 'set Compile / unmanagedSourceDirectories := Seq(baseDirectory.value / "src/main/scala", file('+json.dumps(str(out))+'))'
smoke = 'set Compile / unmanagedSources += file('+json.dumps(str(here/'Smoke.scala'))+')'
command = [str(root/'scripts/with-lock.sh'),'vex-soc','nice','-n','10',
           str(root/'scripts/with-lock.sh'),'sbt-soc','sbt',settings,smoke,'runMain blockexample.Smoke']
with (out/'native.log').open('w') as log:
    process = run_group(command,cwd=root/'SpinalSoc',stdout=log,stderr=log,timeout=120)
print('pass' if process.returncode == 0 and 'BLOCK_COMPOSED_PASS' in (out/'native.log').read_text() else 'inconclusive or failed; see native.log')
raise SystemExit(process.returncode or (0 if 'BLOCK_COMPOSED_PASS' in (out/'native.log').read_text() else 3))
