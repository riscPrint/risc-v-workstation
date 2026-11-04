"""Optional scaffolds with explicit inputs and no inferred hardware behavior."""
import json
from pathlib import Path
import re


def build_files(build, *, sbt_project=None, db_top=None):
    scala_versions = set(re.findall(r'scalaVersion\s*:?=\s*"([^"]+)"', build))
    if scala_versions and scala_versions != {'2.13.14'}:
        raise ValueError('Build wiring supports Scala 2.13.14. Review other Scala versions manually.')
    candidates = sorted(set(re.findall(r'(?:lazy\s+)?val\s+(\w+)\s*=\s*\(?project\b', build)))
    project = sbt_project or (candidates[0] if len(candidates) == 1 else None)
    if project is None:
        raise ValueError('Cannot select one sbt project. Supply --sbt-project with the core project ID.')
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', project) is None:
        raise ValueError('Invalid sbt project ID.')
    if db_top and re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', db_top) is None:
        raise ValueError('--db-top must be a fully qualified no-argument Component class.')
    database = ', ProjectRef(workstation / "SpinalDB/spinaldb", "spinaldb")' if db_top else ''
    return {'rvw/build.sbt': f'''// RVW_HOME selects the installed workstation. Keep core dependencies in its build.
ThisBuild / scalaVersion := "2.13.14"
val workstation = file(sys.env("RVW_HOME")).getCanonicalFile
val coreSource = file(sys.env.getOrElse("RVW_CORE_SOURCE", "..")).getCanonicalFile
lazy val root = (project in file("."))
  .dependsOn(ProjectRef(coreSource, {json.dumps(project)}),
             ProjectRef(workstation / "RiscvSim", "riscvsim"){database})
  .settings(
    name := "rvw-core-adapter",
    fork := true,
    Compile / run / mainClass := Some("rvwcore.Main")
  )
''', 'rvw/project/build.properties': 'sbt.version=1.10.7\n'}


def linker_platform(path, *, region=None, reset_pc=None, name, isa, xlen):
    text = Path(path).read_text()
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    match = re.search(r'\bMEMORY\s*\{([^}]+)\}', text)
    if not match:
        raise ValueError('No literal MEMORY block found in linker script.')
    number = r'(?:0[xX][0-9a-fA-F]+|[0-9]+)[KkMm]?'
    entry = re.compile(rf'\s*(\w+)\s*(?:\([^)]*\))?\s*:\s*ORIGIN\s*=\s*({number})\s*,\s*LENGTH\s*=\s*({number})\s*;?', re.I)
    remaining = match[1]
    regions = {}
    def value(literal):
        suffix = literal[-1].lower()
        factor = {'k': 1024, 'm': 1024 * 1024}.get(suffix, 1)
        digits = literal[:-1] if factor != 1 else literal
        return int(digits, 16 if digits.lower().startswith('0x') else 10) * factor
    while remaining.strip():
        item = entry.match(remaining)
        if item is None:
            raise ValueError('Only literal ORIGIN and LENGTH memory entries are supported. Resolve linker expressions first.')
        label, origin, length = item.groups()
        if label in regions:
            raise ValueError('Duplicate linker memory region: ' + label)
        regions[label] = (value(origin), value(length))
        remaining = remaining[item.end():]
    if region is None and len(regions) == 1:
        region = next(iter(regions))
    if region not in regions:
        raise ValueError('Supply --ram-region with one linker MEMORY region name.')
    if reset_pc is None:
        raise ValueError('--linker-script needs --reset-pc from the core specification.')
    try:
        reset = int(str(reset_pc), 0)
    except ValueError as exc:
        raise ValueError('--reset-pc must be an integer address.') from exc
    base, size = regions[region]
    if size <= 0 or base + size > 1 << xlen or not base <= reset < base + size:
        raise ValueError('RAM and reset PC must fit XLEN; reset PC must be inside selected RAM.')
    platform = dict(name=name, isa=isa, xlen=xlen, reset_pc=hex(reset),
                    ram=[dict(base=hex(base), size=hex(size))], mmio=[], review_required=True)
    return json.dumps(platform, indent=2) + '\n'


def db_script(top, name):
    return f'''#!/usr/bin/env bash
# C6 entry for a reviewed no-argument Component class.
set -euo pipefail
[ "$#" = 2 ] && [ "$1" = default ] || {{ echo 'usage: build-db.sh default OUT' >&2; exit 2; }}
here="$(cd "$(dirname "$0")" && pwd)"
: "${{RVW_HOME:?Set RVW_HOME to the installed workstation}}"
export SPINALDB_PROCESS_RUNNER="$RVW_HOME/SpinalDB/scripts/hdl-deps.py"
export SPINALDB_PYTHON="${{RVW_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}}"
exec "$RVW_HOME/scripts/with-lock.sh" {name} \\
  "$RVW_HOME/scripts/with-lock.sh" sbt nice -n 10 \\
  "$RVW_HOME/SpinalDB/build-db.sh" class {top} "$2" --sbt-dir "$here" --source-root "$here/../src"
'''


def sim_script(name, info_launcher):
    # Keep cheap info output. Other requests use the shipped generic supervisor
    # and identity collector, as the external VexRiscv example does.
    prefix = info_launcher[:info_launcher.index("printf '%s")]
    return prefix + r'''here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "${RVW_HOME:?Set RVW_HOME to the installed workstation checkout}" && pwd)"
sim="$repo/RiscvSim"
export RVW_PYTHON="${RVW_PYTHON:-$repo/rvw/.venv/bin/python}"
if [[ "$RVW_PYTHON" != /* ]] || [ ! -x "$RVW_PYTHON" ]; then
  echo 'Set RVW_PYTHON to an absolute Python interpreter with rvw installed.' >&2
  exit 2
fi
if [ "${1:-}" = --riscvsim-supervised ]; then
  launch_owner="$2"; shift 2
else
  exec "$RVW_PYTHON" "$sim/scripts/supervise.py" "$BASH" "$here/run.sh" "$@"
fi
export RVW_LOCK_PYTHON="$RVW_PYTHON"
if [ "${1:-}" = --core-locked ]; then
  shift
else
  exec "$repo/scripts/with-lock.sh" CORE_LOCK "$BASH" "$here/run.sh" \
    --riscvsim-supervised "$launch_owner" --core-locked "$@"
fi
trap 'exit 143' TERM
trap 'exit 130' INT
trap 'exit 129' HUP
export RVW_CORE_SOURCE="$(cd "${RVW_CORE_SOURCE:-$here/..}" && pwd)"
if [ -n "${RISCVSIM_EXTRA_INPUTS:-}" ]; then
  echo 'input_not_captured:custom_build_layout' >&2
  exit 2
fi
export SPINAL_MAKE_CMD="$sim/scripts/make-jobs.sh"
native_identity="$("$RVW_PYTHON" "$sim/scripts/native-identity.py")"
if [ "${1:-}" = identity ] && [[ "$native_identity" = *'"cache_enabled":false'* ]]; then
  echo 'Native inputs unavailable; refusing identity for result reuse.' >&2
  exit 2
fi
"$RVW_PYTHON" "$sim/scripts/source-identity.py" "$RVW_CORE_SOURCE" "$repo" > "$launch_owner/source.json"
output="$(cd "$here" && "$repo/scripts/with-lock.sh" sbt nice -n 10 \
  sbt -J-Xmx3g -batch 'root/compile' 'export root/Runtime/fullClasspath' 2>&1)" || {
  echo "$output" >&2; exit 2;
}
cp="$(printf '%s\n' "$output" | grep -v '^\[' | grep 'scala-library' | tail -1)"
if [ -z "$cp" ]; then echo "$output" >&2; echo 'No classpath in sbt output.' >&2; exit 2; fi
exec "$RVW_PYTHON" "$sim/scripts/native-identity.py" launch "$native_identity" "$launch_owner" \
  -Xss64m -Xmx"${RISCVSIM_XMX:-3g}" -XX:+UseParallelGC \
  -Driscvsim.cwd="$PWD" -Driscvsim.script="$here/run.sh" \
  -Driscvsim.tools="$repo" -Driscvsim.source="$launch_owner/source.json" \
  -cp "$cp" rvwcore.Main "$@"
'''.replace('CORE_LOCK', name)
