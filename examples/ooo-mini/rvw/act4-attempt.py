#!/usr/bin/env python3
"""Repeat the bounded ACT4 configuration attempt. This does not run the DUT."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--checkout', type=Path, required=True, help='Private pinned ACT4 checkout.')
parser.add_argument('--out', type=Path, required=True)
parser.add_argument('--z3-library', type=Path, required=True)
args = parser.parse_args()
out = args.out.resolve()
out.mkdir(parents=True, exist_ok=False)
inputs = out/'inputs'
inputs.mkdir()
project = Path(__file__).resolve().parent.parent
home = Path(os.environ['RVW_HOME']).resolve()
# Reuse the existing instruction-only M-mode bootstrap. Keep every test body
# and signature check. PMP stays at the real four-entry count.
base = home/'examples/vexriscv/rvw/act4'
profile = json.loads((base/'profile.json').read_text())
profile['test_extensions'] = ['zifencei']
profile['platform'] = 'platform.json'
profile['params'].update(NUM_PMP_ENTRIES=4, MISALIGNED_LDST=True, MTVEC_MODES=[0,1],
                         REPORT_VA_IN_MTVAL_ON_BREAKPOINT=False, MARCHID_IMPLEMENTED=True)
profile['limits'] = [
    'Instruction-only M-mode profile on the M/U core. Reduced CSR boot; no standard Sm qualification.',
    'Signature generation uses model-only CLINT and interrupt generator. DUT devices are disabled for this batch.',
    'One Zifencei group has a 115-second build budget.']
(inputs/'profile.json').write_text(json.dumps(profile, indent=2)+'\n')
platform = json.loads((project/'rvw/platform.json').read_text())
platform['privilege_modes'] = 'M'
(inputs/'platform.json').write_text(json.dumps(platform, indent=2)+'\n')
sail = json.loads((base/'sail.json').read_text())
sail['memory']['pmp']['usable_count'] = 4
sail['memory']['misaligned']['exceptions']['load_store'] = {'None': None}
sail['memory']['misaligned']['byte_by_byte'] = True
sail['base']['mtvec']['vectored']['supported'] = True
(inputs/'sail.json').write_text(json.dumps(sail, indent=2)+'\n')
for name in ('rvmodel_macros.h', 'link.ld'):
    shutil.copyfile(base/name, inputs/name)
# Use the documented macOS UDB workaround in a private cache.
cache = out/'cache'
z3 = cache/'udb/z3/z3-5.1.0/arm64'
z3.mkdir(parents=True)
assert args.z3_library.is_file()
(z3/'libz3.so').symlink_to(args.z3_library.resolve())
env = dict(os.environ, XDG_CACHE_HOME=str(cache), PYTHONDONTWRITEBYTECODE='1')
command = [str(home/'rvw/.venv/bin/rvw'), '--project', str(project), 'regress', 'act4-build',
           '--profile', str(inputs/'profile.json'), '--checkout', str(args.checkout.resolve()),
           '--out', str(out/'build'), '--timeout', '115']
with (out/'command.log').open('w') as log:
    completed = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT)
manifest = json.loads((out/'build/manifest.json').read_text())
print(json.dumps(dict(status=manifest['status'], built=len(manifest['tests']), dut='NOT RUN')))
raise SystemExit(0 if completed.returncode == 0 and manifest['status'] == 'built' else 1)
