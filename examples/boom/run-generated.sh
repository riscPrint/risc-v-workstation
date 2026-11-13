#!/usr/bin/env bash
# Build and run the RV64 families selected by verification.json.
set -euo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo"
export RVW_HOME="$repo"
: "${SPINAL_BOOM:?Set SPINAL_BOOM to the private BOOM clone}"
python="$repo/rvw/.venv/bin/python"
rvw="$repo/rvw/.venv/bin/rvw"
out="$($python -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "${1:?Supply a new output directory}")"
mkdir "$out"
"$rvw" regress plan --features examples/boom/verification.json --json > "$out/plan.json"
"$python" - "$out/matrix.json" <<'PY'
import json, sys
from rvw.regress.mmu import load
from pathlib import Path
path = Path(sys.argv[1])
path.write_text(json.dumps({'schema': 'rvw.mmu/1', 'matrix': {'modes': ['sv39']}}))
cases = load(path)
# The profile implements no ASID bits and uses fault-based A/D updates.
cases = [case for case in cases if case.get('ad_mode') != 'hardware']
for case in cases:
    if 'asid' in case:
        case['asid'] = 0
path.write_text(json.dumps({'schema': 'rvw.mmu/1', 'scenarios': cases}))
PY
"$rvw" regress mmu build "$out/matrix.json" --out "$out/mmu" --json > "$out/mmu-build.json"
for pair in controls:controls pmp:pmp wfi:spike-wfi random:random-transitions scheduled:scheduled-wfi; do
  family="${pair%%:*}"; description="${pair#*:}"
  "$rvw" regress privilege build "examples/privilege/$description.json" \
    --out "$out/$family" --json > "$out/$family-build.json"
done
"$python" RiscvSim/tests/ordering/suite.py --xlen 64 --seed 1 \
  --suite lrsc --suite amo --suite amo-fault --suite fence --suite fence-i \
  --out "$out/ordering" > "$out/ordering-build.json"
for source in "$out"/ordering/*.S; do
  riscv64-unknown-elf-gcc -nostdlib -nostartfiles \
    -march=rv64ima_zicsr_zifencei -mabi=lp64 \
    "-Wl,-T,$out/ordering/link.ld" "$source" -o "${source%.S}.elf"
done
"$python" - "$out" <<'PY'
from pathlib import Path
import sys
out = Path(sys.argv[1])
text = Path('examples/boom/rvw.toml').read_text()
for family in ('mmu', 'controls', 'pmp', 'ordering', 'wfi', 'random'):
    cycles = 200000 if family == 'ordering' else 30000
    text += (f'\n[suites.expanded-{family}]\ndir = "{out / family}"\n'
             'glob = "*.elf"\nstrip_suffix = ".elf"\nconfigs = ["small"]\n'
             f'max_cycles = {cycles}\ntimeout_s = 120\n')
text += '\n' + (out / 'scheduled/suite.toml').read_text().replace(
    'dir = "."', f'dir = "{out / "scheduled"}"')
(out / 'run.toml').write_text(text)
PY
suites=expanded-mmu,expanded-controls,expanded-pmp,expanded-ordering,expanded-wfi,expanded-random
suites+=,scheduled-wfi-3-0,scheduled-wfi-3-1,scheduled-wfi-7-0,scheduled-wfi-7-1,scheduled-wfi-11-0,scheduled-wfi-11-1
status=0
scripts/with-lock.sh boom nice -n 10 "$rvw" regress run --core "$out/run.toml" \
  --suite "$suites" --config small --jobs 4 --rvfi-trace \
  --out "$out/results" --json > "$out/results.json" || status=$?
"$rvw" regress cosim "$out/results" --platform rvw/configs/act4/boom/platform.json \
  --out "$out/strict-spike.json" --json > "$out/strict-spike-summary.json" || status=$?
exit "$status"
