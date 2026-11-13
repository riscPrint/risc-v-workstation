#!/usr/bin/env bash
# C6 navigation entry for the Verilog top (Yosys front end; see rvw query build-hdl).
set -euo pipefail
[ "$#" = 2 ] && [ "$1" = default ] || { echo 'usage: build-db.sh default OUT' >&2; exit 2; }
here="$(cd "$(dirname "$0")" && pwd)"
: "${RVW_HOME:?Set RVW_HOME to the installed workstation}"
exec nice -n 10 "${RVW_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}" -m rvw query build-hdl \
  --top picorv32 --out "$2" --frontend slang --define RISCV_FORMAL --param PROGADDR_RESET=2147483648 --param PROGADDR_IRQ=2147483664 --param ENABLE_MUL=1 --param ENABLE_DIV=1 "$here/../picorv32.v"
