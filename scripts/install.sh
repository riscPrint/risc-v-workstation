#!/usr/bin/env bash
# Install the workstation once. Core projects stay in separate repositories.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

usage() {
  cat <<'HELP'
Usage: scripts/install.sh [OPTIONS]
  --prefix DIR       Clone into DIR (default: current checkout, or
                     $HOME/tools/risc-v-workstation for a standalone script).
  --source DIR       Clone a local checkout instead of GitHub (needs --prefix).
  --with-arcilator   Pinned CIRCT binaries outside the repository.
  --with-sim         JDK 21, sbt 1.10.7+, Verilator 5+, make and C++ compiler.
  --with-riscv-dv    Pinned native pygen in $RVW_RISCV_DV or ~/.cache/rvw.
  --with-riscv-gcc   Bare-metal RISC-V GCC and binutils.
  --with-cosim       Spike headers/libraries and the workstation shim.
  --with-ric3        Build pinned rIC3 outside the checkout (Rust nightly).
  --with-ebmc        Build pinned EBMC outside the checkout (make, flex, bison).
  --with-pono|--with-avy|--with-suprove
  --with-bitwuzla|--with-cvc5|--with-yices
                     Enable an installed engine or fetch an external pinned suite.
  --with-formal      OSS CAD Suite plus a pinned native yosys-slang build.
  --with-ooo         Build the optional C integer OoO scheduler.
  --with-gem5        Native RISC-V gem5 v25.1.0.1 (build with two jobs).
  --with-lint        Pinned native Verible syntax and style lint.
  --with-sail        Pinned Sail model.
  --with-act4|--with-riscv-tests|--with-riscv-formal
                     Acquire pinned verification source inputs.
  --with-typed-waves Build the pinned SpinalWaves checker and typed viewer (Cargo).
  --from-bundle      Use native workflow artifacts for selected tools.
  --bundle-run ID    Download artifacts from this private Actions run (needs gh).
  --bundle-dir DIR   Use artifacts saved in DIR. No artifact network requests.
  --profile NAME     minimal, verification, formal, arch or all (inventory).
  --all              Select the legacy tool set.
                     Use --profile all for the full inventory.
  --shell-rc FILE    Add the env.sh source line to FILE. Default: print it only.
  --yes             Approve package commands without a prompt.
  --dry-run         Print actions. Do not write files or install packages.
  --check           Report requested tools and versions. Do not change files.
  -h, --help        Show this help.
System package commands require approval unless --yes is set.
Python 3.11+ is required. Local downloads go under RVW_HOME/.tools.
RVW_GEM5 selects an existing gem5 executable path. It must be v25.1.0.1
with RISC-V support. An invalid selection is an error.
HELP
}
fail() { printf 'install.sh: %s\n' "$*" >&2; exit 2; }
show() { printf '  +'; printf ' %q' "$@"; printf '\n'; }
run() { show "$@"; if [ "$dry" = 0 ]; then "$@"; fi; }
value() { [ "$#" -ge 2 ] && [ -n "$2" ] && [[ "$2" != --* ]] || fail "$1 needs a value"; }

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Expand profiles from the same packaged data used by rvw doctor.
for arg in "$@"; do
  if [ "$arg" = --profile ]; then
    expanded=$(python3 "$script_root/scripts/tool-inventory.py" --expand "$@") || exit 2
    expanded_args=()
    while IFS= read -r arg; do [ -z "$arg" ] || expanded_args+=("$arg"); done <<< "$expanded"
    set -- ${expanded_args[@]+"${expanded_args[@]}"}
    break
  fi
done
managed_sources=()
extra_tools=()
arc=0 ric3=0 ebmc=0
suite_engines=()
dv=0 sim=0 gcc=0 cosim=0 formal=0 gem5=0 ooo=0 yes=0 dry=0 check=0
prefix='' source_dir='' shell_rc=''
waves=0 lint=0 bundle=0 sail=0 bundle_run='' bundle_dir=''
while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix) value "$@"; prefix="$2"; shift 2 ;;
    --source) value "$@"; source_dir="$2"; shift 2 ;;
    --shell-rc) value "$@"; shell_rc="$2"; shift 2 ;;
    --from-bundle) bundle=1; shift ;;
    --bundle-run) value "$@"; bundle_run="$2"; shift 2 ;;
    --bundle-dir) value "$@"; bundle_dir="$2"; shift 2 ;;
    --with-typed-waves) waves=1; shift ;;
    --with-lint) lint=1; shift ;;
    --with-act4|--with-riscv-tests|--with-riscv-formal) managed_sources+=("${1#--with-}"); shift ;;
    --with-sail) sail=1; shift ;;
    --with-arcilator) arc=1; shift ;;
    --with-sim) sim=1; shift ;;
    --with-riscv-dv) dv=1; shift ;;
    --with-riscv-gcc) gcc=1; shift ;;
    --with-cosim) cosim=1; shift ;;
    --with-ric3) ric3=1; shift ;;
    --with-ebmc) ebmc=1; shift ;;
    --with-pono|--with-avy|--with-suprove|--with-bitwuzla|--with-cvc5|--with-yices)
      suite_engines+=("${1#--with-}"); shift ;;
    --with-formal) formal=1; shift ;;
    --with-ooo) ooo=1; shift ;;
    --with-gem5) gem5=1; shift ;;
    --all) arc=1; dv=1; waves=1; lint=1; sim=1; gcc=1; cosim=1; formal=1; gem5=1; ooo=1; shift ;;
    --yes) yes=1; shift ;;
    --dry-run) dry=1; shift ;;
    --check) check=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --with-*) extra_tools+=("${1#--with-}"); shift ;;
    *) fail "unknown argument: $1" ;;
  esac
done
[ "$dry" = 0 ] || [ "$check" = 0 ] || fail '--check and --dry-run are separate modes'
[ -z "$source_dir" ] || [ -n "$prefix" ] || fail '--source needs --prefix'
script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -z "$prefix" ]; then
  if [ -f "$script_root/rvw/pyproject.toml" ]; then prefix="$script_root";
  else prefix="$HOME/tools/risc-v-workstation"; fi
fi
# Use absolute paths without creating directories in check or dry-run mode.
[[ "$prefix" = /* ]] || prefix="$PWD/$prefix"
[[ "$prefix" != *$'\n'* ]] || fail 'prefix must not contain a newline'
if [ -n "$source_dir" ]; then
  source_dir="$(cd "$source_dir" && pwd)"
  [ -f "$source_dir/rvw/pyproject.toml" ] || fail '--source is not a workstation checkout'
fi
rvw_home="$prefix"
tools="$rvw_home/.tools"
# Source identities are immutable. Host package versions can drift.
# Matches the tested Homebrew source timestamp and installed headers.
verilator_revision=ea338be98e1e838d3518809ce8899f85a009963c
spike_revision=eff659cd43d7eafb7f3559bceed2540eabb31c50
gcc_revision=a33dac0251d17a7b74d99bd8fd401bfce87d2aed
oss_version=2026-10-22
gem5_version=25.1.0.1
gem5_revision=c8222cc67a399bfc01e8658dd14b30d5bfd634f9
gem5_source="$tools/src/gem5-v$gem5_version"
gem5_external=0
if [ -n "${RVW_GEM5:-}" ]; then gem5_external=1;
else RVW_GEM5="$gem5_source/build/RISCV/gem5.opt"; fi
[[ "$RVW_GEM5" = /* ]] || RVW_GEM5="$PWD/$RVW_GEM5"
[[ "$RVW_GEM5" != *$'\n'* ]] || fail 'RVW_GEM5 must not contain a newline'
if [ -x "$tools/gem5/bin/gem5.opt" ] && [ "$gem5_external" = 0 ]; then RVW_GEM5="$tools/gem5/bin/gem5.opt"; fi
if [ -d "$tools/verilator" ]; then export VERILATOR_ROOT="$tools/verilator/share/verilator"; fi
if [ -x "$tools/sail/bin/sail_riscv_sim" ]; then export RVW_SAIL="$tools/sail/bin/sail_riscv_sim"; fi
export RVW_GEM5
export RVW_SLANG="${RVW_SLANG:-$tools/lib/slang.so}"
export PATH="$tools/verible/bin:$tools/verilator/bin:$tools/sail/bin:$PATH"
export PATH="$rvw_home/rvw/.venv/bin:$tools/bin:$tools/oss-cad-suite/bin:$PATH:$HOME/.local/bin"
# Reuse installer-managed tools on a second run without sourcing env.sh first.
if [ -d "$tools/jdk" ]; then export JAVA_HOME="$tools/jdk"; fi
if [ -n "${JAVA_HOME:-}" ]; then export PATH="$JAVA_HOME/bin:$PATH"; fi
if [ -z "${SPIKE_PREFIX:-}" ]; then
  if command -v spike >/dev/null 2>&1; then SPIKE_PREFIX="$(dirname "$(dirname "$(command -v spike)")")";
  else SPIKE_PREFIX="$tools/spike"; fi
fi
if [ "$bundle" = 1 ]; then SPIKE_PREFIX="$tools/spike"; fi
export SPIKE_PREFIX
export PATH="$HOME/.cache/rvw/formal-engines/bin:$tools/riscv/bin:$PATH"
case ":$PATH:" in *":$SPIKE_PREFIX/bin:"*) ;; *) export PATH="$SPIKE_PREFIX/bin:$PATH" ;; esac

system="$(uname -s)"
pm=''
case "$system" in
  Darwin) pm=brew ;;
  Linux)
    if [ -r /etc/os-release ]; then
      # os-release is supplied by the OS, not the target checkout.
      . /etc/os-release
      case " ${ID:-} ${ID_LIKE:-} " in
        *debian*|*ubuntu*) pm=apt ;;
        *fedora*|*rhel*|*centos*) pm=dnf ;;
      esac
    fi ;;
esac
if [ -z "$pm" ]; then
  printf '%s\n' 'Unsupported OS. Install Python 3.11+, git and uv manually.' \
    'Create rvw/.venv with uv venv --python python3 rvw/.venv.' \
    "Install with: uv sync --locked --no-dev --extra mcp --project rvw" \
    "Native tools: https://github.com/riscPrint/risc-v-workstation/blob/main/docs/BRING_YOUR_OWN_CORE.md#install-the-workstation"
  exit 1
fi

# Every system mutation has its own approval and displays its exact command.
package() {
  local command=()
  if [ "$pm" = brew ]; then
    command=(env HOMEBREW_NO_AUTO_UPDATE=1 brew "$@")
  elif [ "$(id -u)" = 0 ]; then command=("$@");
  else command=(sudo "$@"); fi
  show "${command[@]}"
  [ "$dry" = 0 ] || return 0
  if [ "$yes" = 0 ]; then
    local answer=''
    printf 'Run this system package command? [y/N] '
    read -r answer || true
    case "$answer" in y|Y|yes|YES) ;; *) fail 'package command declined; nothing more was installed' ;; esac
  fi
  "${command[@]}"
}
updated=0
packages() {
  case "$pm" in
    brew)
      command -v brew >/dev/null || fail 'Install Homebrew first: https://brew.sh'
      package install "$@" ;;
    apt)
      if [ "$updated" = 0 ]; then package apt-get update; updated=1; fi
      package env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$@" ;;
    dnf) package dnf install -y "$@" ;;
  esac
}
version_ge() {
  local actual="$1" required="$2" a b c x y z
  IFS=. read -r a b c <<< "$actual"
  IFS=. read -r x y z <<< "$required"
  a=$((10#${a:-0})); b=$((10#${b:-0})); c=$((10#${c:-0}))
  x=$((10#${x:-0})); y=$((10#${y:-0})); z=$((10#${z:-0}))
  (( a > x || (a == x && b > y) || (a == x && b == y && c >= z) ))
}
# Does not launch a JVM for sbt. --script-version reads its launcher version.
probe() {
  local label="$1" minimum="$2" output number
  shift 2
  if ! command -v "$1" >/dev/null 2>&1; then printf 'MISSING %s\n' "$label"; return 1; fi
  if ! output=$("$@" 2>&1); then printf 'UNUSABLE %s: %s\n' "$label" "$output"; return 1; fi
  if [[ "$output" =~ ([0-9]+\.[0-9]+(\.[0-9]+)?) ]]; then number="${BASH_REMATCH[1]}";
  elif [[ "$output" =~ ([0-9]+) ]]; then number="${BASH_REMATCH[1]}";
  else printf 'UNKNOWN VERSION %s: %s\n' "$label" "$output"; return 1; fi
  if [ "$label" = 'JDK' ] || [ "$label" = 'javac' ]; then
    if [[ "$number" != 21 && "$number" != 21.* ]]; then
      printf 'WRONG VERSION %s: %s (need 21)\n' "$label" "$number"; return 1
    fi
  elif ! version_ge "$number" "$minimum"; then
    printf 'TOO OLD %s: %s (need %s+)\n' "$label" "$number" "$minimum"; return 1
  fi
  tested=''
  case "$label" in
    Verilator) tested=5.052 ;;
    Yosys) tested=0.70 ;;
    SymbiYosys) tested=0.70 ;;
    Yices) tested=2.7.0 ;;
    Spike) tested=1.1.1 ;;
    Sail) tested=0.15 ;;
    sbt) tested=1.11.7 ;;
    JDK|javac) tested=21.0.13 ;;
  esac
  if [ -n "$tested" ] && [ "$number" != "$tested" ]; then
    printf 'WARNING %s %s: outside tested version table (%s); see docs/TOOL_VERSIONS.md\n' "$label" "$number" "$tested"
  fi
  if [ "$label" = Verilator ] && [ "$number" = 5.049 ]; then
    printf 'WARNING Verilator 5.049: known FSM coverage crash; keep FSM coverage disabled\n'
  fi
  printf 'PRESENT %s: %s\n' "$label" "$number"
}
core_check() {
  local failed=0
  probe Python 3.11 "$python_cmd" --version || failed=1
  probe uv 0.13.6 uv --version || failed=1
  probe git 2 git --version || failed=1
  if [ -x "$rvw_home/rvw/.venv/bin/python" ]; then
    probe 'rvw venv Python' 3.11 "$rvw_home/rvw/.venv/bin/python" --version || failed=1
    if ! "$rvw_home/rvw/.venv/bin/python" -B -I -c 'from importlib.metadata import version; print("PRESENT rvw:", version("rvw")); print("PRESENT mcp:", version("mcp")); print("PRESENT jsonschema:", version("jsonschema"))'; then failed=1; fi
    "$rvw_home/rvw/.venv/bin/rvw" --help >/dev/null || failed=1
  else printf 'MISSING rvw venv: %s\n' "$rvw_home/rvw/.venv"; failed=1; fi
  if [ -f "$rvw_home/env.sh" ]; then printf 'PRESENT env.sh\n';
  else printf 'MISSING env.sh\n'; failed=1; fi
  return "$failed"
}
sim_check() {
  local failed=0
  probe JDK 21 java -version || failed=1
  probe javac 21 javac -version || failed=1
  probe sbt 1.10.7 sbt --script-version || failed=1
  probe Verilator 5 verilator --version || failed=1
  probe make 3 make --version || failed=1
  probe C++ 0 "${CXX:-c++}" --version || failed=1
  return "$failed"
}
gem5_check() {
  local output number
  if [ ! -f "$RVW_GEM5" ] || [ ! -x "$RVW_GEM5" ]; then
    printf 'MISSING gem5: %s\n' "$RVW_GEM5"; return 1
  fi
  # gem5 has no --version option. Build info also identifies the guest ISA.
  if ! output=$(nice "$RVW_GEM5" --build-info 2>&1); then
    printf 'UNUSABLE gem5: %s\n' "$output"; return 1
  fi
  number=$(printf '%s\n' "$output" | sed -n 's/^gem5 version //p')
  if [ "$number" != "$gem5_version" ]; then
    printf 'WRONG VERSION gem5: %s (need %s)\n' "${number:-unknown}" "$gem5_version"; return 1
  fi
  if ! printf '%s\n' "$output" | grep -Eq '^[[:space:]]*USE_RISCV_ISA = True[[:space:]]*$'; then
    printf 'MISSING gem5 RISC-V support: %s\n' "$RVW_GEM5"; return 1
  fi
  printf 'PRESENT gem5: %s (RISC-V) %s\n' "$number" "$RVW_GEM5"
}
spike_inputs() {
  local part
  for part in include/riscv/processor.h include/fesvr include/softfloat include/fdt lib/libdisasm.a lib/libfesvr.a; do
    [ -e "$SPIKE_PREFIX/$part" ] || return 1
  done
  [ -f "$SPIKE_PREFIX/lib/libriscv.so" ] || [ -f "$SPIKE_PREFIX/lib/libriscv.dylib" ] || [ -f "$SPIKE_PREFIX/lib/libriscv.a" ]
}
optional_check() {
  local failed=0
  if [ "$waves" = 1 ]; then
    for wave_tool in spinalwaves-check surfer-tywaves; do
      if [ ! -x "$tools/bin/$wave_tool" ]; then
        printf 'MISSING typed viewer tool: %s\n' "$tools/bin/$wave_tool"; failed=1
      elif ! "$tools/bin/$wave_tool" --version; then
        printf 'UNUSABLE typed viewer tool: %s\n' "$wave_tool"; failed=1
      fi
    done
    if [ ! -f "$tools/share/spinalwaves/source.tar.gz" ] || [ ! -f "$tools/share/spinalwaves/LICENSE-EUPL-1.2.txt" ] || [ ! -f "$tools/share/spinalwaves/vendor-lock.json" ]; then
      printf 'MISSING typed viewer source or notices\n'; failed=1
    fi
  fi
  if [ "$lint" = 1 ]; then "$python_cmd" "$rvw_home/scripts/install-verible.py" --home "$rvw_home" --check || failed=1; fi
  if [ "$dv" = 1 ]; then "$python_cmd" "$rvw_home/scripts/install-riscv-dv.py" --check || failed=1; fi
  if [ "$ooo" = 1 ]; then
    "$rvw_home/rvw/.venv/bin/python" -m rvw.ooo.native --check "$tools/ooo/libooo.so" || failed=1
  fi
  if [ "$gem5" = 1 ]; then gem5_check || failed=1; fi
  if [ "$sim" = 1 ]; then sim_check || failed=1; fi
  if [ "$gcc" = 1 ]; then
    probe 'RISC-V GCC' 10 riscv64-unknown-elf-gcc --version || failed=1
    probe 'RISC-V binutils' 2 riscv64-unknown-elf-objdump --version || failed=1
  fi
  if [ "$cosim" = 1 ]; then
    probe Spike 1 spike --help || failed=1
    if spike_inputs; then printf 'PRESENT Spike headers and libraries: %s\n' "$SPIKE_PREFIX";
    else printf 'MISSING Spike headers/libraries: %s\n' "$SPIKE_PREFIX"; failed=1; fi
    if ! "$rvw_home/rvw/.venv/bin/python" -B -I - "$rvw_home/Cosim/build/librvw_spike.so" <<'PYTHON'
import ctypes, hashlib, json, pathlib, sys
from rvw.cosim.spike import SHIM_SOURCE, SHIM_VERSION
from rvw.cosim.build import build_id
try:
    path = pathlib.Path(sys.argv[1])
    manifest = json.loads(path.with_name(path.name + '.manifest.json').read_text())
    digest = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    source_hash = digest(SHIM_SOURCE)
    if (manifest['schema'] != 'rvw.spike-build/1'
        or manifest['shim_version'] != SHIM_VERSION
        or manifest['shim_source_sha256'] != source_hash
        or manifest['shim_sha256'] != digest(path)
        or manifest['spike_library_sha256'] != digest(manifest['spike_library'])
        or manifest['build_id'] != build_id(manifest['build_inputs'])):
        raise ValueError('shim manifest does not match installed inputs')
    lib = ctypes.CDLL(str(path))
    lib.rvw_shim_version.restype = ctypes.c_uint
    lib.rvw_shim_source_sha256.restype = ctypes.c_char_p
    lib.rvw_shim_build_sha256.restype = ctypes.c_char_p
    if (lib.rvw_shim_version() != SHIM_VERSION
        or lib.rvw_shim_source_sha256().decode() != source_hash
        or lib.rvw_shim_build_sha256().decode() != manifest['build_id']):
        raise ValueError('shim embedded identity does not match')
    print('PRESENT Spike shim: version', SHIM_VERSION)
except (OSError, ValueError, KeyError, AttributeError) as error:
    sys.exit('MISSING or unusable Spike shim: ' + str(error))
PYTHON
    then failed=1; fi
  fi
  if [ "$ric3" = 1 ]; then probe rIC3 0 rIC3 --version || failed=1; fi
  if [ "$ebmc" = 1 ]; then probe EBMC 0 ebmc --version || failed=1; fi
  for suite_engine in ${suite_engines[@]+"${suite_engines[@]}"}; do
    case "$suite_engine" in yices) suite_executable=yices-smt2 ;; *) suite_executable="$suite_engine" ;; esac
    if command -v "$suite_executable" >/dev/null 2>&1; then
      printf 'PRESENT %s; native qualification is separate\n' "$suite_engine"
    else
      printf 'MISSING %s\n' "$suite_engine"
      failed=1
    fi
  done
  if [ "$formal" = 1 ]; then
    probe Yosys 0.46 yosys -V || failed=1
    probe SymbiYosys 0 sby --version || failed=1
    probe Yices 2 yices-smt2 --version || failed=1
    # Optional portfolio engines do not gate the base formal installation.
    for engine in yosys-abc pono btorsim avy rIC3 ebmc; do
      if command -v "$engine" >/dev/null; then
        printf 'PRESENT optional formal engine: %s\n' "$engine"
      else
        printf 'not_installed optional formal engine: %s\n' "$engine"
      fi
    done
    if [ ! -f "$RVW_SLANG" ] || ! yosys -Q -T -m "$RVW_SLANG" -p 'help read_slang' >/dev/null 2>&1; then
      printf 'MISSING native yosys-slang: %s\n' "$RVW_SLANG"; failed=1
    else printf 'PRESENT native yosys-slang: %s\n' "$RVW_SLANG"; fi
    if command -v yosys >/dev/null && yosys -Q -T -p 'help xprop' 2>&1 | grep -q 'No such command'; then
      printf 'MISSING Yosys xprop support\n'; failed=1
    fi
  fi
  if [ "$sail" = 1 ] && [ -z "${RVW_SAIL:-}" ]; then printf 'MISSING Sail\n'; failed=1; fi
  if [ -n "${RVW_SAIL:-}" ]; then probe Sail 0.15 "$RVW_SAIL" --version || failed=1; fi
  if [ "$arc" = 1 ]; then "$RVW_PYTHON" -m rvw.sim.arcilator_install --check || failed=1; fi
  return "$failed"
}
verify_archive() {
  run "$RVW_PYTHON" -I -c 'import hashlib,pathlib,sys; actual=hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest(); sys.exit(0 if actual == sys.argv[2] else "archive checksum mismatch")' "$1" "$2"
}
pinned_source() {
  local url="$1" directory="$2" revision="$3"
  if [ ! -d "$directory/.git" ]; then
    run git init "$directory"
    run git -C "$directory" remote add origin "$url"
    run git -C "$directory" fetch --depth 1 origin "$revision"
    run git -C "$directory" checkout --detach FETCH_HEAD
  fi
  if [ "$dry" = 0 ]; then
    [ "$(git -C "$directory" rev-parse HEAD)" = "$revision" ] &&
      git -C "$directory" diff --quiet HEAD -- || fail "Source must be clean at $revision: $directory"
  else printf 'Verify source is clean at %s\n' "$revision"; fi
  run git -C "$directory" submodule update --init --recursive
}
# Use this archive where the distro has no JDK 21 package.
temurin_jdk() {
  local arch jdk_url
  command -v curl >/dev/null || packages curl ca-certificates
  arch="$(uname -m)"
  case "$arch" in x86_64) arch=x64 ;; aarch64|arm64) arch=aarch64 ;; *) fail "No Temurin JDK for $arch" ;; esac
  run mkdir -p "$tools/downloads" "$tools/jdk21"
  case "$arch" in
    x64) checksum=d7f5d5cf865a2902b70ff549b97586a7d3f234e016f041ab447ea740c7d66d1c ;;
    aarch64) checksum=e3522e707fc7dbe2a72c30746b1e7068301a0213ecd213d4491f35a14eb55578 ;;
  esac
  jdk_url="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/OpenJDK21U-jdk_${arch}_linux_hotspot_21.0.13_9.tar.gz"
  run curl -fL --retry 3 "$jdk_url" -o "$tools/downloads/jdk.tar.gz"
  verify_archive "$tools/downloads/jdk.tar.gz" "$checksum"
  run tar -xzf "$tools/downloads/jdk.tar.gz" --strip-components=1 -C "$tools/jdk21"
  export JAVA_HOME="$tools/jdk21"
}

python_cmd=python3
# An unversioned uv request can select system Python even when PATH starts in a venv.
# Keep the established base interpreter so profile changes retain its packages.
if [ -x "$rvw_home/rvw/.venv/bin/python" ] && probe Python 3.11 "$rvw_home/rvw/.venv/bin/python" --version >/dev/null 2>&1; then
  existing_python=$("$rvw_home/rvw/.venv/bin/python" -c 'import sys; print(sys._base_executable)')
  if [[ "$existing_python" = /* ]] && [ -x "$existing_python" ]; then python_cmd="$existing_python"; fi
fi
if ! probe Python 3.11 "$python_cmd" --version >/dev/null 2>&1 && command -v python3.11 >/dev/null 2>&1; then
  python_cmd=python3.11
fi
# cocotb 2.1 supports Python through 3.14. Select only installed interpreters.
for extra_tool in ${extra_tools[@]+"${extra_tools[@]}"}; do
  case "$extra_tool" in cocotb|pyuvm)
    python_supported='import sys; sys.exit(not ((3, 11) <= sys.version_info[:2] < (3, 15)))'
    if ! "$python_cmd" -c "$python_supported" >/dev/null 2>&1; then
      compatible_python=''
      for candidate in python3.11 python3.12 python3.13 python3.14; do
        # A venv can retain a versioned alias after switching its base Python.
        # Check every PATH match and pass uv the validated absolute path.
        while IFS= read -r candidate_path; do
          if "$candidate_path" -c "$python_supported" >/dev/null 2>&1; then
            compatible_python="$candidate_path"; break
          fi
        done < <(type -aP "$candidate" 2>/dev/null || true)
        [ -z "$compatible_python" ] || break
      done
      [ -n "$compatible_python" ] || fail 'cocotb and pyuvm need Python 3.11 through 3.14; put a compatible versioned interpreter on PATH'
      python_cmd="$compatible_python"
      printf 'Select %s for cocotb and pyuvm\n' "$python_cmd"
    fi
    break ;;
  esac
done

if [ "$bundle" = 1 ] && [ "$check" = 0 ]; then
  [ -n "$bundle_run" ] || [ -n "$bundle_dir" ] || fail '--from-bundle needs --bundle-run or --bundle-dir'
fi
if [ "${#extra_tools[@]}" -gt 0 ] && { [ "$check" = 1 ] || [ "$dry" = 1 ]; }; then
  inventory_mode=()
  if [ "$check" = 1 ]; then inventory_mode+=(--check);
  elif [ "$dry" = 1 ]; then inventory_mode+=(--dry-run); fi
  python3 "$script_root/scripts/tool-inventory.py" "${inventory_mode[@]}" --extra ${extra_tools[@]+"${extra_tools[@]}"} || exit $?
fi
export RVW_PYTHON="$rvw_home/rvw/.venv/bin/python"
if [ "$check" = 1 ]; then
  failed=0
  for dependency in ${managed_sources[@]+"${managed_sources[@]}"}; do
    PYTHONPATH="$rvw_home/rvw/src" "$python_cmd" -m rvw doctor --resolve "$dependency" || failed=1
  done
  if [ "$sail" = 1 ] && [ "$bundle" = 0 ]; then
    RVW_SAIL="$(PYTHONPATH="$rvw_home/rvw/src" "$python_cmd" -m rvw doctor --resolve sail)" || failed=1
    export RVW_SAIL
  fi
  core_check || failed=1
  optional_check || failed=1
  exit "$failed"
fi
if [ "$gem5" = 1 ] && [ "$gem5_external" = 1 ]; then
  gem5_check || fail 'RVW_GEM5 is invalid; select a native RISC-V gem5 v25.1.0.1 executable'
fi

# Install only missing core tools. uv uses the OS Python, with no hidden downloads.
if ! command -v git >/dev/null; then packages git; fi
if ! probe Python 3.11 "$python_cmd" --version; then
  case "$pm" in
    brew)
      packages python@3.11
      if [ "$dry" = 0 ]; then export PATH="$(brew --prefix python@3.11)/libexec/bin:$PATH"; fi ;;
    apt)
      packages python3 python3-venv
      if [ "$dry" = 0 ] && ! probe Python 3.11 python3 --version >/dev/null; then
        packages python3.11 python3.11-venv
        python_cmd=python3.11
      fi ;;
    dnf) packages python3.11 python3.11-pip; python_cmd=python3.11 ;;
  esac
  [ "$dry" = 1 ] || probe Python 3.11 "$python_cmd" --version || fail 'Install Python 3.11+ on this OS, then retry'
fi
local_uv=0
if ! probe uv 0.13.6 uv --version; then
  case "$pm" in
    brew) packages uv ;;
    dnf)
      # uv is in Fedora. RHEL can use pip when its repos do not provide uv.
      if [ "$dry" = 1 ] || dnf -q list --available uv >/dev/null 2>&1; then packages uv;
      else
        packages python3.11-pip
        run "$python_cmd" -m pip install --user --upgrade uv
        local_uv=1
      fi ;;
    apt)
      packages pipx python3-venv ca-certificates
      run pipx install --force uv
      local_uv=1
      ;;
  esac
fi
if [ -e "$rvw_home" ]; then
  [ -f "$rvw_home/rvw/pyproject.toml" ] && [ -f "$rvw_home/Cosim/build.sh" ] || fail "prefix is not a workstation checkout: $rvw_home"
else
  run mkdir -p "$(dirname "$rvw_home")"
  if [ -n "$source_dir" ]; then run git clone --no-hardlinks "$source_dir" "$rvw_home";
  else run git clone https://github.com/riscPrint/risc-v-workstation.git "$rvw_home"; fi
fi
if [ "$local_uv" = 1 ]; then
  run mkdir -p "$tools/bin"
  run ln -sf "$HOME/.local/bin/uv" "$tools/bin/uv"
fi
# Validate the lock before uv can replace an existing development environment.
run uv lock --check --no-managed-python --project "$rvw_home/rvw" --python "$python_cmd"
run uv venv --python "$python_cmd" --no-managed-python --allow-existing "$rvw_home/rvw/.venv"
run uv sync --locked --inexact --no-dev --extra mcp --no-managed-python --project "$rvw_home/rvw" --python "$python_cmd"
export RVW_PYTHON="$rvw_home/rvw/.venv/bin/python"
export RVW_LOCK_PYTHON="$RVW_PYTHON"
if [ "${#extra_tools[@]}" -gt 0 ] && [ "$dry" = 0 ]; then
  package_words=$("$RVW_PYTHON" "$script_root/scripts/tool-inventory.py" --packages "$pm" --extra ${extra_tools[@]+"${extra_tools[@]}"}) || exit 2
  package_args=()
  while IFS= read -r word; do [ -z "$word" ] || package_args+=("$word"); done <<< "$package_words"
  if [ "${#package_args[@]}" -gt 0 ]; then packages "${package_args[@]}"; fi
  "$RVW_PYTHON" "$script_root/scripts/tool-inventory.py" --home "$rvw_home" --packages-done --extra ${extra_tools[@]+"${extra_tools[@]}"} || exit $?
fi

if [ "$dv" = 1 ]; then
  dv_args=()
  [ "$dry" = 0 ] || dv_args+=(--dry-run)
  run "$python_cmd" "$script_root/scripts/install-riscv-dv.py" ${dv_args[@]+"${dv_args[@]}"}
fi

if [ "$lint" = 1 ]; then
  lint_args=(--home "$rvw_home")
  [ "$dry" = 0 ] || lint_args+=(--dry-run)
  run "$python_cmd" "$script_root/scripts/install-verible.py" ${lint_args[@]+"${lint_args[@]}"}
fi

if [ "$bundle" = 1 ]; then
  bundle_args=(--home "$rvw_home")
  [ -z "$bundle_run" ] || bundle_args+=(--run "$bundle_run")
  [ -z "$bundle_dir" ] || bundle_args+=(--directory "$bundle_dir")
  [ "$sim" = 0 ] || bundle_args+=(--tool verilator)
  [ "$gcc" = 0 ] || bundle_args+=(--tool gcc)
  [ "$cosim" = 0 ] || bundle_args+=(--tool spike)
  [ "$gem5" = 0 ] || bundle_args+=(--tool gem5)
  [ "$sail" = 0 ] || bundle_args+=(--tool sail)
  run "$RVW_PYTHON" "$rvw_home/scripts/native-bundle.py" install "${bundle_args[@]}"
  if [ "$sim" = 1 ]; then export VERILATOR_ROOT="$tools/verilator/share/verilator"; fi
  if [ "$gem5" = 1 ]; then RVW_GEM5="$tools/gem5/bin/gem5.opt"; export RVW_GEM5; gem5_external=1; fi
  if [ "$sail" = 1 ]; then export RVW_SAIL="$tools/sail/bin/sail_riscv_sim"; fi
fi

if [ "$sim" = 1 ]; then
  if ! probe JDK 21 java -version || ! probe javac 21 javac -version; then
    case "$pm" in
      brew)
        packages openjdk@21
        if [ "$dry" = 0 ]; then export JAVA_HOME="$(brew --prefix openjdk@21)/libexec/openjdk.jdk/Contents/Home";
        else export JAVA_HOME='/path/from/brew/openjdk@21/libexec/openjdk.jdk/Contents/Home'; fi ;;
      apt)
        if apt-cache show openjdk-21-jdk-headless >/dev/null 2>&1; then
          packages openjdk-21-jdk-headless
          if [ "$dry" = 0 ]; then
            JAVA_HOME=$(find /usr/lib/jvm -maxdepth 1 -type d -name '*21*' | sort | head -n 1)
            [ -n "$JAVA_HOME" ] || fail 'Cannot find the installed JDK 21'
            export JAVA_HOME
          fi
        else temurin_jdk; fi ;;
      dnf) temurin_jdk ;;
    esac
    if [ "$dry" = 1 ] && [ -z "${JAVA_HOME:-}" ]; then export JAVA_HOME=/path/to/jdk21; fi
    export PATH="$JAVA_HOME/bin:$PATH"
    run mkdir -p "$tools"
    run ln -sfn "$JAVA_HOME" "$tools/jdk"
  fi
  if ! probe Verilator 5 verilator --version; then
    [ "$bundle" = 0 ] || [ "$dry" = 1 ] || fail 'Bundled Verilator is unusable'
    packages verilator
  fi
  if ! command -v make >/dev/null || ! command -v "${CXX:-c++}" >/dev/null; then
    case "$pm" in
      brew) fail 'Install the Xcode command line tools with xcode-select --install, then retry' ;;
      apt) packages build-essential ;;
      dnf) packages make gcc-c++ ;;
    esac
  fi
  if ! probe sbt 1.10.7 sbt --script-version; then
    if [ "$pm" = brew ]; then packages sbt;
    else
      command -v curl >/dev/null || packages curl ca-certificates
      run mkdir -p "$tools/downloads" "$tools/bin"
      url=https://github.com/sbt/sbt/releases/download/v1.10.7/sbt-1.10.7.tgz
      run curl -fL --retry 3 "$url" -o "$tools/downloads/sbt.tgz"
      verify_archive "$tools/downloads/sbt.tgz" 32c15233c636c233ee25a2c31879049db7021cfef70807c187515c39b96b0fe6
      run tar -xzf "$tools/downloads/sbt.tgz" -C "$tools"
      run ln -sf ../sbt/bin/sbt "$tools/bin/sbt"
    fi
  fi
fi
if [ "$gcc" = 1 ] && ! probe 'RISC-V GCC' 10 riscv64-unknown-elf-gcc --version; then
  [ "$bundle" = 0 ] || [ "$dry" = 1 ] || fail 'Bundled GCC is unusable'
  case "$pm" in
    brew) package tap riscv-software-src/riscv; packages riscv-software-src/riscv/riscv-gnu-toolchain ;;
    apt) packages gcc-riscv64-unknown-elf binutils-riscv64-unknown-elf ;;
    dnf)
      packages autoconf automake python3 libmpc-devel mpfr-devel gmp-devel gawk bison flex texinfo patchutils gcc gcc-c++ zlib-devel expat-devel make diffutils which
      run mkdir -p "$tools/src"
      pinned_source https://github.com/riscv-collab/riscv-gnu-toolchain.git "$tools/src/riscv-gnu-toolchain" "$gcc_revision"
      run bash -c 'cd "$1" && ./configure --prefix="$2" --with-arch=rv64gc --with-abi=lp64d' _ "$tools/src/riscv-gnu-toolchain" "$tools/riscv"
      run nice make -C "$tools/src/riscv-gnu-toolchain" -j2 ;;
  esac
fi
if [ "$cosim" = 1 ] && [ "$bundle" = 0 ]; then
  if ! spike_inputs; then
    case "$pm" in
      brew) if ! command -v dtc >/dev/null 2>&1; then packages dtc; fi ;;
      apt) packages build-essential device-tree-compiler ;;
      dnf) packages make gcc-c++ dtc ;;
    esac
    run mkdir -p "$tools/src"
    pinned_source https://github.com/riscv-software-src/riscv-isa-sim.git "$tools/src/spike" "$spike_revision"
    run mkdir -p "$tools/src/spike/build"
    run bash -c 'cd "$1" && ../configure --prefix="$2" --without-boost --without-boost-asio --without-boost-regex' _ "$tools/src/spike/build" "$SPIKE_PREFIX"
    run nice make -C "$tools/src/spike/build" -j2
    run make -C "$tools/src/spike/build" install
    run mkdir -p "$SPIKE_PREFIX/share/rvw"
    if [ "$dry" = 0 ]; then
      printf '{"version":"1.1.1-dev","revision":"%s","origin":"rvw-source-build"}\n' "$spike_revision" > "$SPIKE_PREFIX/share/rvw/spike-source.json"
    fi
  fi
  export PATH="$SPIKE_PREFIX/bin:$PATH"
  run env PATH="$rvw_home/rvw/.venv/bin:$PATH" SPIKE_PREFIX="$SPIKE_PREFIX" nice "$rvw_home/Cosim/build.sh"
fi
if [ "$ric3" = 1 ]; then
  case "$pm" in
    brew) packages gmp mpfr ;;
    apt) packages libgmp-dev libmpfr-dev ;;
    dnf) packages gmp-devel mpfr-devel ;;
  esac
fi
if [ "$ebmc" = 1 ]; then
  case "$pm" in
    brew) packages bison flex make curl ;;
    apt) packages build-essential bison flex curl patch ;;
    dnf) packages gcc-c++ bison flex make curl patch ;;
  esac
fi
for optional_engine in ric3 ebmc; do
  case "$optional_engine" in ric3) selected="$ric3" ;; ebmc) selected="$ebmc" ;; esac
  if [ "$selected" = 1 ]; then
    engine_args=()
    if [ "$dry" = 1 ]; then engine_args+=(--dry-run); fi
    run "$RVW_PYTHON" "$rvw_home/scripts/install-formal-engine.py" "$optional_engine" ${engine_args[@]+"${engine_args[@]}"}
  fi
done
for suite_engine in ${suite_engines[@]+"${suite_engines[@]}"}; do
  suite_args=()
  if [ "$dry" = 1 ]; then suite_args+=(--dry-run); fi
  run "$RVW_PYTHON" "$rvw_home/scripts/install-formal-suite.py" "$suite_engine" ${suite_args[@]+"${suite_args[@]}"}
done
if [ "$formal" = 1 ]; then
  if ! probe Yosys 0.46 yosys -V || ! probe SymbiYosys 0 sby --version || ! probe Yices 2 yices-smt2 --version; then
    command -v curl >/dev/null || packages curl ca-certificates
    arch="$(uname -m)"
    case "$arch" in x86_64) arch=x64 ;; aarch64|arm64) arch=arm64 ;; *) fail "No OSS CAD Suite archive for $arch" ;; esac
    case "$system" in Darwin) os=darwin ;; Linux) os=linux ;; esac
    run mkdir -p "$tools/downloads"
    case "$os-$arch" in
      darwin-arm64) checksum=378e87e60db8cb3d077c63613cbed75e52306cf5ebdfeb95596629f343e536c0 ;;
      darwin-x64) checksum=de02f14693cdd7f1bb9b83f2f77dc8a36eca1c6c552f7934549f4bbb1de4d8f5 ;;
      linux-arm64) checksum=b113c673c31925d7ac91a8b7a2654339bb6670fd44323c9b350a458c4c043349 ;;
      linux-x64) checksum=45b7401d677f1e6cffb19dcaafb8e92c95a49dfc05b332ae4d00b84c94f62f6e ;;
      *) fail "No OSS CAD Suite archive for $os-$arch" ;;
    esac
    oss_url="https://github.com/YosysHQ/oss-cad-suite-build/releases/download/$oss_version/oss-cad-suite-$os-$arch-${oss_version//-/}.tgz"
    run curl -fL --retry 3 "$oss_url" -o "$tools/downloads/oss-cad-suite.tgz"
    verify_archive "$tools/downloads/oss-cad-suite.tgz" "$checksum"
    run tar -xzf "$tools/downloads/oss-cad-suite.tgz" -C "$tools"
  fi
  if [ ! -f "$RVW_SLANG" ] || ! yosys -Q -T -m "$RVW_SLANG" -p 'help read_slang' >/dev/null 2>&1; then
    command -v cmake >/dev/null || packages cmake
    command -v make >/dev/null || packages make
    command -v c++ >/dev/null || fail 'Install a C++20 compiler, then retry --with-formal'
    run "$RVW_PYTHON" "$rvw_home/scripts/build-yosys-slang.py" --prefix "$tools" --yosys-config "$(command -v yosys-config || printf yosys-config)"
    export RVW_SLANG="$tools/lib/slang.so"
  fi
fi
if [ "$gem5" = 1 ] && [ "$gem5_external" = 0 ] && ! gem5_check; then
  # Match Python headers and python-config to the interpreter used by SCons.
  gem5_python="$python_cmd"
  case "$pm" in
    brew)
      command -v xcrun >/dev/null && xcrun clang++ --version >/dev/null 2>&1 ||
        fail 'Install the Xcode command line tools with xcode-select --install, then retry'
      packages python@3.14 protobuf gperftools libpng pkgconf zlib m4
      if [ "$dry" = 0 ]; then
        gem5_brew="$(brew --prefix)"
        gem5_python="$(brew --prefix python@3.14)/bin/python3.14"
      else
        gem5_brew=/path/from/brew
        gem5_python="$gem5_brew/opt/python@3.14/bin/python3.14"
      fi
      export CPATH="$gem5_brew/include${CPATH:+:$CPATH}"
      export LIBRARY_PATH="$gem5_brew/lib${LIBRARY_PATH:+:$LIBRARY_PATH}"
      ;;
    apt)
      packages build-essential "${python_cmd}-dev" "${python_cmd}-venv" \
        zlib1g-dev m4 pkg-config libprotobuf-dev protobuf-compiler \
        libprotoc-dev libgoogle-perftools-dev libpng-dev
      ;;
    dnf)
      packages gcc gcc-c++ make "${python_cmd}-devel" zlib-devel m4 \
        pkgconf-pkg-config protobuf-devel protobuf-compiler \
        gperftools-devel libpng-devel
      ;;
  esac
  if [ "$dry" = 0 ]; then
    # PATH can select rvw's venv. python-config belongs to its base Python.
    gem5_python="$("$gem5_python" -I -c 'import sys; print(sys._base_executable)')"
    command -v "$gem5_python-config" >/dev/null || fail "Missing Python build config: $gem5_python-config"
  fi
  run uv venv --python "$gem5_python" --no-managed-python --allow-existing "$tools/gem5-venv"
  run uv pip install --python "$tools/gem5-venv/bin/python" 'scons==4.11.1'
  run mkdir -p "$tools/src"
  if [ ! -e "$gem5_source" ]; then
    run git clone --depth 1 --branch "v$gem5_version" https://github.com/gem5/gem5.git "$gem5_source"
  fi
  if [ "$dry" = 0 ]; then
    [ -d "$gem5_source/.git" ] &&
      [ "$(git -C "$gem5_source" rev-parse HEAD)" = "$gem5_revision" ] &&
      git -C "$gem5_source" diff --quiet HEAD -- ||
      fail "gem5 source must be clean at $gem5_revision: $gem5_source"
  else printf 'Verify gem5 source is clean at %s\n' "$gem5_revision"; fi
  export PYTHON_CONFIG="$gem5_python-config"
  # Use a native build root and the RISC-V defconfig on both host systems.
  if [ ! -d "$gem5_source/build/RISCV/gem5.build" ]; then
    run "$rvw_home/scripts/with-lock.sh" gem5 nice "$tools/gem5-venv/bin/scons" \
      -C "$gem5_source" defconfig "$gem5_source/build/RISCV" "$gem5_source/build_opts/RISCV" --ignore-style
  fi
  run "$rvw_home/scripts/with-lock.sh" gem5 nice "$tools/gem5-venv/bin/scons" \
    -C "$gem5_source" "$RVW_GEM5" -j2 --ignore-style
  if [ "$dry" = 0 ]; then gem5_check || fail 'Native gem5 build check failed'; fi
fi

if [ "$waves" = 1 ]; then
  if [ "$dry" = 0 ]; then
    command -v cargo >/dev/null || fail 'Install Rust/Cargo, then retry --with-typed-waves'
  fi
  run env CARGO_BUILD_JOBS=2 "$rvw_home/scripts/with-lock.sh" sbt nice -n 10 \
    bash "$rvw_home/SpinalWaves/scripts/install.sh" --copy --prefix "$tools/bin"
fi

if [ "$ooo" = 1 ]; then
  run nice -n 10 "$rvw_home/rvw/.venv/bin/python" -m rvw.ooo.native --build "$tools/ooo/libooo.so"
fi

if [ "$arc" = 1 ]; then
  run "$rvw_home/rvw/.venv/bin/python" -m rvw.sim.arcilator_install
fi

# Use the CLI resolver for source and archive pins. Never duplicate its inventory.
for dependency in ${managed_sources[@]+"${managed_sources[@]}"}; do
  run "$RVW_PYTHON" -m rvw doctor --resolve "$dependency" --acquire
  if [ "$dry" = 0 ]; then
    resolved="$("$RVW_PYTHON" -m rvw doctor --resolve "$dependency")"
    case "$dependency" in
      act4) export ACT4_SOURCE="$resolved" ;;
      riscv-tests) export RISCV_TESTS_SRC="$resolved" ;;
      riscv-formal) export RISCV_FORMAL="$resolved" ;;
    esac
  fi
done
if [ "$sail" = 1 ] && [ "$bundle" = 0 ]; then
  run "$RVW_PYTHON" -m rvw doctor --resolve sail --acquire
  if [ "$dry" = 0 ]; then export RVW_SAIL="$("$RVW_PYTHON" -m rvw doctor --resolve sail)"; fi
fi

# Quote values for both bash and zsh. Do not change shell startup files by default.
printf 'Write %s\n' "$rvw_home/env.sh"
if [ "$dry" = 0 ]; then
  {
    printf '# Generated by scripts/install.sh. Source this file in bash or zsh.\n'
    if [ "$arc" = 1 ]; then printf 'export RVW_CIRCT=%q\n' "${RVW_CIRCT:-$HOME/.cache/rvw/circt/firtool-1.163.0}"; fi
    printf 'export RVW_HOME=%q\n' "$rvw_home"
    printf 'export RVW_PYTHON=%q\nexport RVW_LOCK_PYTHON=%q\n' "$RVW_PYTHON" "$RVW_LOCK_PYTHON"
    if [ "$gem5" = 1 ] || [ -x "$RVW_GEM5" ]; then printf 'export RVW_GEM5=%q\n' "$RVW_GEM5"; fi
    if [ -n "${JAVA_HOME:-}" ]; then
      printf 'export JAVA_HOME=%q\nexport PATH="$JAVA_HOME/bin:$PATH"\n' "$JAVA_HOME"
    fi
    if [ -n "${VERILATOR_ROOT:-}" ]; then printf 'export VERILATOR_ROOT=%q\n' "$VERILATOR_ROOT"; fi
    for variable in ACT4_SOURCE RISCV_TESTS_SRC RISCV_FORMAL; do
      if [ -n "${!variable:-}" ]; then printf 'export %s=%q\n' "$variable" "${!variable}"; fi
    done
    if [ -n "${RVW_SAIL:-}" ]; then printf 'export RVW_SAIL=%q\n' "$RVW_SAIL"; fi
    if [ "$formal" = 1 ]; then printf 'export RVW_SLANG=%q\n' "$RVW_SLANG"; fi
    printf 'export PATH="$RVW_HOME/.tools/verible/bin:$RVW_HOME/.tools/verilator/bin:$RVW_HOME/.tools/sail/bin:$PATH"\n'
    printf 'export PATH="$HOME/.cache/rvw/formal-engines/bin:$PATH"\n'
    printf 'export SPIKE_PREFIX=%q\nexport PATH="$SPIKE_PREFIX/bin:$PATH"\n' "$SPIKE_PREFIX"
    printf 'export PATH="$RVW_HOME/rvw/.venv/bin:$RVW_HOME/.tools/bin:$RVW_HOME/.tools/oss-cad-suite/bin:$RVW_HOME/.tools/riscv/bin:$PATH"\n'
  } > "$rvw_home/env.sh"
fi
printf -v source_line 'source %q' "$rvw_home/env.sh"
printf 'Add this line to your shell startup file:\n%s\n' "$source_line"
if [ -n "$shell_rc" ]; then
  printf 'Add source line to %s if absent\n' "$shell_rc"
  if [ "$dry" = 0 ] && ! grep -Fqx "$source_line" "$shell_rc" 2>/dev/null; then
    printf '\n%s\n' "$source_line" >> "$shell_rc"
  fi
fi
run "$rvw_home/rvw/.venv/bin/rvw" --help
if [ "$dry" = 0 ]; then
  core_check || fail 'Core self-check failed'
  optional_check || fail 'Requested native tool self-check failed'
fi
printf '%s\n' 'Next: put the project files in your core repository.' \
  'https://github.com/riscPrint/risc-v-workstation/blob/main/docs/BRING_YOUR_OWN_CORE.md#put-the-project-files-in-your-core-repository'
