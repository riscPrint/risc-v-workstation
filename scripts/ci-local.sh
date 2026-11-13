#!/usr/bin/env bash
# Run the same checks in Actions and in a disposable local work directory.
set -euo pipefail
mode="${1:-fast}"
case "$mode" in fast|nightly-python|nightly-scala|messages) ;; *) echo "usage: $0 [fast|nightly-python|nightly-scala|messages]" >&2; exit 2 ;; esac
root="$(cd "$(dirname "$0")/.." && pwd)"
# Commit policy needs only the standard library and the event's Git history.
if [ "$mode" = messages ]; then
  exec "${CI_PYTHON:-python3}" "$root/scripts/check-conventional.py"
fi
job="$(mktemp -d "${TMPDIR:-/tmp}/rvw-ci.XXXXXXXX")"
cleanup() {
  status=$?
  trap - EXIT
  # Tests publish read-only result generations. Restore owner access in this
  # job's private directory before removal. Do not follow directory symlinks.
  chmod -R -P u+rwX "$job"
  rm -rf "$job"
  exit "$status"
}
trap cleanup EXIT
export RVW_CI_SOURCE="$root" RVW_CI_WORK="$job/work"
echo "Local CI mode: $mode"
# Copy tracked files, including local edits. Exclude all old build output and venvs.
"${CI_PYTHON:-python3.11}" - <<'PY'
import os, pathlib, shutil, subprocess
src = pathlib.Path(os.environ['RVW_CI_SOURCE'])
dst = pathlib.Path(os.environ['RVW_CI_WORK'])
dst.mkdir()
for name in subprocess.check_output(['git', '-C', str(src), 'ls-files', '-z']).decode().split('\0'):
    if not name:
        continue
    source = src / name
    if not source.exists() and not source.is_symlink():
        continue
    target = dst / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        target.symlink_to(os.readlink(source))
    else:
        shutil.copy2(source, target)
PY
cd "$job/work"
# Tests that need Git get an isolated repository, never the contributor's Git dir.
git init -q
git config user.name 'Local CI'
git config user.email 'ci@localhost'
git add .
git commit -qm 'ci(local): prepare isolated work directory'
export TMPDIR="$job/tmp"
mkdir -p "$TMPDIR"
unset RVW_HOME RVW_PROJECT RVW_CORE RVW_LOCKS_HELD RVW_LOCK_PYTHON PYTHONPATH VIRTUAL_ENV
# Optional core tests must never find a neighbouring developer checkout.
export SPINAL_BOOM="$job/no-boom" VEXRISCV="$job/no-vex"
export RVW_RESULTS="$job/results" RVW_SRC_CACHE="$job/src-cache"
"${CI_PYTHON:-python3.11}" -m venv rvw/.venv
export PATH="$PWD/rvw/.venv/bin:$PATH"
export RVW_LOCK_PYTHON="$PWD/rvw/.venv/bin/python"
lock() { scripts/with-lock.sh "$1" nice -n 10 "${@:2}"; }
# Fail before test setup if metadata changed without its lock.
lock suite uv lock --check --project rvw
lock suite uv sync --locked --extra dev --extra mcp --project rvw --no-managed-python --python "$PWD/rvw/.venv/bin/python"
export CARGO_BUILD_JOBS=2
export SBT_OPTS="${SBT_OPTS:-} -Dsbt.task.cpus=2"
scala() { (cd "$1"; "$RVW_CI_WORK/scripts/with-lock.sh" sbt nice -n 10 sbt -batch -J-XX:ActiveProcessorCount=2 "${@:2}"); }
pytest_report() {
  local report="$1" budget="$2" status=0 summary_status=0
  shift 2
  lock suite python -m pytest rvw/tests "$@" --junitxml="$report" || status=$?
  # Publish counts even when pytest fails. Never hide the original test exit.
  if [ -f "$report" ]; then
    if [ -n "$budget" ]; then
      python scripts/ci-test-summary.py "$report" --max-seconds "$budget" || summary_status=$?
    else
      python scripts/ci-test-summary.py "$report" || summary_status=$?
    fi
  else
    echo "Python JUnit report missing; counts unavailable." >&2
    summary_status=1
  fi
  if [ "$status" -ne 0 ]; then return "$status"; fi
  return "$summary_status"
}
case "$mode" in
  fast)
    pytest_report fast-results.xml 300 -m fast --strict-markers -q -ra --durations=10
    (cd vscode; "$RVW_CI_WORK/scripts/with-lock.sh" suite nice -n 10 bash -e -c 'npm ci; npm run typecheck; npm run build; npm test')
    (cd SpinalTrace; "$RVW_CI_WORK/scripts/with-lock.sh" suite nice -n 10 cargo test --locked -p spinaltrace-rs)
    scala SpinalWaves/spinalwaves 'testOnly spinalwaves.NamingSpec spinalwaves.EmitterSpec'
    ;;
  nightly-python)
    pytest_report nightly-results.xml "" --strict-markers -q -ra --durations=20
    ;;
  nightly-scala)
    scala SpinalKonata test inputs/test
    scala SpinalDB/spinaldb Test/compile
    scala SpinalChecks Test/compile
    ;;
  messages)
    # The policy reads the original event and Git history, but never changes it.
    (cd "$root"; "$RVW_CI_WORK/scripts/with-lock.sh" suite nice -n 10 python scripts/check-conventional.py)
    ;;
esac
