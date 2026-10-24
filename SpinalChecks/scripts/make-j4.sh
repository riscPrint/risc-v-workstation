#!/usr/bin/env bash
# GNU make with at most RVW_MAKE_JOBS (default 4) jobs: SpinalSim runs `make -j<all cores>` for
# Verilator; point SPINAL_MAKE_CMD here to stay within the machine's shared-resource rules.
args=()
for a in "$@"; do case "$a" in -j*) ;; *) args+=("$a") ;; esac; done
exec make -j"${RVW_MAKE_JOBS:-4}" "${args[@]}"
