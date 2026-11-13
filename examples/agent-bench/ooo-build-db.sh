#!/usr/bin/env bash
set -euo pipefail
[[ "$1" = default ]] || exit 2
out="$2"
cd "$OOO_MINI_SOURCE"
if [ -f examples/ooo-mini/build.sbt ]; then cd examples/ooo-mini; fi
rm -f rvw/out/design.db
"$RVW_HOME/scripts/with-lock.sh" "${RVW_SBT_LOCK:-sbt-agentbench}" nice -n 15 sbt -J-Xmx3g -batch -Dsbt.offline=true 'runMain ooomini.BuildDb'
cp rvw/out/design.db "$out"
