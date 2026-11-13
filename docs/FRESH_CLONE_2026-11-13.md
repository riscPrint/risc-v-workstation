# Fresh checkout qualification, 2026-11-13

The public VexRiscv example passed three ISA tests on macOS ARM64. The add
trace matched a new Spike build. A separate PicoRV32 project created with
`rvw init` passed its smoke program. These are simulator results. They do not
qualify the whole cores, all install profiles, Linux, or hardware. The final clean
CI run had no test failures. It still exceeded the 300-second time target.

The first complete passing ISA trace with a Spike match was available about
41 minutes 42 seconds after clone creation. This includes fix work and tests.
The start uses the new `.git` directory creation time, with one-second
resolution. The clone command itself took 28.98 seconds. Independent preparation
and fix tests overlapped. This is an observed qualification session, not a
sequential unattended install benchmark.

## Isolation and inputs

`$CHECKOUT` is the new workstation clone. `$CACHE` is a new private cache.
`$HOME` in the command table is a new private home. `$RUN_ROOT` contains all
three. None of these names refer to an existing developer checkout or cache.
Qualification commands used a rebuilt environment and `nice -n 10`.
The early CI wrapper and CI script each added nice 10, so those test runs
used effective nice 20. The last CI run uses only the script's built-in nice
10; its pytest priority was checked with ps. These runs are not a paired
performance comparison.
No `RVW_*` setting was inherited. The clean clone had no existing `env.sh`;
the successful installer generated it before it was sourced. The trial set
`XDG_CACHE_HOME`, `UV_CACHE_DIR`,
`COURSIER_CACHE`, `RVW_RESULTS`, `RVW_SRC_CACHE` and `RVW_LOCK_DIR` below `$CACHE`.
The private home's `.cache` was moved below `$CACHE` and linked back. Java used
an explicit private `user.home`; later commands also set `java.io.tmpdir`.
CI reports were moved outside the checkout and `CI_REPORT_DIR` then selected
that location. Default CI reports otherwise make the workstation tree dirty.

PATH contained system commands, Python and uv, the documented JDK 21,
OSS CAD Suite, RISC-V GCC, and private launchers. Homebrew was available for
installer plans. No system package mutation was approved or run. A separate
sbt distribution was fetched because the existing launcher was in a user
Coursier cache. No old venv, private core, Spike shim or RVW cache was reused.

- Initial workstation revision: `42d8068c9919380f1fb664e614db72d3c4eb3d1c`.
- VexRiscv source: `baf7dc82f855eddaf5b0a20a6802c526f127e38a`.
- PicoRV32 source: `ef203c2b0a3fb793280f5114941416c425c5b461`.
- riscv-tests: `3df703cd52d5f0d8224e3c50bf03c6cb70efff98`; its env submodule was fetched.
- Spike source: `eff659cd43d7eafb7f3559bceed2540eabb31c50`; shim version 8.
- Host tools: JDK 21.0.13, sbt launcher 1.11.7 with project sbt 1.10.7,
  uv 0.13.6, RISC-V GCC 15.1.0, and Verilator 5.049.
- Verilator 5.049 produced the documented version and FSM coverage warnings.
  No FSM coverage qualification is claimed. The tested table names 5.052.
- The base install selected Python 3.15.2. Its cocotb 2.1.0 build rejected
  Python 3.15. The compatible-interpreter fix is listed below.

The trial used this environment pattern. Set `TOOLS_PATH` to system commands
and the documented native tools on the host. Create the named directories
before use. Keep `JAVA_HOME` host-specific. The local harness also used private
sbt and Python launchers and captured each command's wall time and exit code.

```sh
RUN_ROOT="$PWD/fresh-trial"
CHECKOUT="$RUN_ROOT/ws"
CACHE="$RUN_ROOT/cache"
mkdir -p "$CACHE" "$RUN_ROOT/home"
gh repo clone riscPrint/risc-v-workstation "$CHECKOUT"
env -i HOME="$RUN_ROOT/home" USER=freshclone PATH="$TOOLS_PATH" \
  JAVA_HOME="$JAVA_HOME" TMPDIR="$CACHE" XDG_CACHE_HOME="$CACHE" \
  UV_CACHE_DIR="$CACHE/uv" COURSIER_CACHE="$CACHE/coursier" \
  RVW_RESULTS="$CACHE/results" RVW_SRC_CACHE="$CACHE/source" \
  RVW_LOCK_DIR="$CACHE/locks" CI_REPORT_DIR="$CACHE/ci-reports" \
  JAVA_TOOL_OPTIONS="-Duser.home=$RUN_ROOT/home -Djava.io.tmpdir=$CACHE" \
  SBT_OPTS="-Dsbt.global.base=$CACHE/sbt -Dsbt.boot.directory=$CACHE/sbt-boot -Dsbt.ivy.home=$CACHE/ivy" \
  nice -n 10 /bin/bash
```

Run each command from the ledger inside that shell. For `ci-local.sh`, use a
shell without the outer `nice`: the script applies nice 10 itself. This avoids
the early trial's effective nice 20. Read README, the install section in
BRING_YOUR_OWN_CORE and AGENT_SETUP before the installer. The workstation repository was private during this trial. Clone and pull
required an account with repository access. The private HOME had no GitHub credentials. One final pull therefore failed
before any test ran. The retry used the host Git credential helper for the Git
transport only and passed. No token was copied into the private HOME. File
reads and earlier Git pulls used to deliver fixes were not timed. The ledger records executed
qualification shell commands; each PR also states its repair tests.

Main changed during this trial. Fixes were merged and pulled before later
checks. The successful first ISA run used workstation `d08126ff`; its first
Spike comparison used `ba9155a6`. It compared captured trace bytes, not a new
RTL run at the later revision. The local setup commits added workstation
project files. The VexRiscv core Scala source stayed at its upstream pin.
No unchanged-revision gate acceptance is claimed.

## Step results

| Step | First attempt | Result |
|---|---|---|
| GitHub workstation clone | Worked first time | 28.98 s |
| Minimal install | Needed a fix | macOS arrays, package pruning and interpreter changes; repeat install repaired |
| Verification profile | Needed a fix | Python 3.15 rejected; Python portion later passed on 3.11; unused native tools excluded |
| Source env.sh | Worked after a documented step | Minimal install generated the file |
| Doctor | Needed a fix | Public example config list differed from adapter; optional empty suites remain not ready |
| Fast CI tier | Needed a fix | Python command selection, Bash arrays and a historical source fixture; workflow entry repaired on main; final time target still failed |
| VexRiscv fetch | Worked first time | Public pinned source; no private core |
| ISA ELF build and list | Needed a fix | Missing source-fetch step and mandatory VEXRISCV variable |
| Scala dependency fetch | Needed a fix | Guide lacked an executable cold-cache fetch command |
| VexRiscv ISA regression | Worked after a documented step | 3 pass, 0 inconclusive; add, beq and lw; --jobs 1 |
| Spike install and shim | Needed a fix | Installer asked for dtc despite its presence; new source build and shim passed |
| Spike comparison | Worked first time | Complete passing add trace; 504 instructions and 4 traps |
| Database and query | Worked after a documented step | Fresh database and source location for rvfi_rd_wdata |
| MCP core list | Worked first time | regress_list and cosim_check present; listing is not runtime proof |
| Separate rvw init project | Worked first time | Mapped PicoRV32 project created outside workstation |
| Separate project run | Worked after a documented step | Smoke ELF built; one C1 pass with a fresh instance |

The Spike comparison used one declared `csr_reset_unknown` synchronization
for `mscratch` reset state. It reported `trace_complete: true` and
`end_status: pass`. It did not prove all CSR state or full ISA compliance.
The database had 3 components, 1047 signals, 178 registers and one memory.
It reported six missing-provider PDG warnings. A source-location query passed;
complete dependency-graph coverage is not claimed.

Early build attempts were bounded at 120 seconds. Exit 124 in the command
ledger means that the qualification harness stopped the command. It is not a
core failure or a pass. Scala preparation was then completed separately under
the private sbt lock. Spike make resumed its own fresh partial build between
bounded steps. The final model build took 48.44 seconds, the three-test
regression 65.41 seconds, the comparison 7.45 seconds, and the separate
PicoRV32 smoke command 64.96 seconds.

## Fixes

| PR | Classification | Change |
|---|---|---|
| [#1271](https://github.com/riscPrint/risc-v-workstation/pull/1271) | Installer defect; shell version | Handle empty optional arrays with macOS Bash 3.2 |
| [#1279](https://github.com/riscPrint/risc-v-workstation/pull/1279) | Installer/CI path defect | Use the installed Python without requiring the python3.11 alias |
| [#1289](https://github.com/riscPrint/risc-v-workstation/pull/1289) | Installer defect | Reuse dtc on PATH |
| [#1294](https://github.com/riscPrint/risc-v-workstation/pull/1294) | Installer defect | Preserve installed Python extras on profile changes |
| [#1299](https://github.com/riscPrint/risc-v-workstation/pull/1299) | Generated launcher defect; shell version | Handle empty HDL include arrays with macOS Bash |
| [#1302](https://github.com/riscPrint/risc-v-workstation/pull/1302) | Version problem | Select an installed Python supported by cocotb and pyuvm |
| [#1329](https://github.com/riscPrint/risc-v-workstation/pull/1329) | Installer defect | Keep the existing venv base interpreter on repeat installs |
| [#1345](https://github.com/riscPrint/risc-v-workstation/pull/1345) | Installer path/version defect | Skip an incompatible versioned alias and validate all PATH matches |
| [#1306](https://github.com/riscPrint/risc-v-workstation/pull/1306) | Example path defect | Default to the copied project root; retain explicit external source selection |
| [#1307](https://github.com/riscPrint/risc-v-workstation/pull/1307) | Example configuration defect | Declare the exact adapter configurations; keep doctor strict |
| [#1354](https://github.com/riscPrint/risc-v-workstation/pull/1354) | Documentation error | Give pinned test-source and online Scala fetch commands; correct the old private-BOOM dependency statement |
| [#1418](https://github.com/riscPrint/risc-v-workstation/pull/1418) | Fresh CI test dependency | Keep the exact pinned OoO mutation source as a checked test fixture; require no Git history |

The original clean fast tier had 3042 passes, 4 skips and one VHDL launcher
failure in 624.02 seconds. It also failed the 300-second time target. Later
results are recorded below. The target was not raised. Full verification,
formal, architecture and all-profile installs were not completed. Their large
optional tools were checked with plans only, as required for this trial.
Optional `dv-baseline` and `act4` suites had no built ELFs. Doctor correctly
keeps these suites not ready. A passing ISA subset does not qualify them.

## Disk and downloads

Sizes are incremental for this host, with the stated native prerequisites
already present. They are not clean-OS install estimates. Exact network wire
bytes were not captured. Cache size is not download size. The first cache snapshot followed a failed
verification attempt. It is not an isolated minimal-profile cache footprint.
The disposable trial root used about 2.1 GiB at one pre-cleanup checkpoint.

| Profile or required component | Disk observed | Download observation |
|---|---|---|
| Base CLI and MCP | 28.55 MiB minimal venv; 44.21 MiB mixed uv cache at first snapshot | At least 5.9 MiB of named large wheels; exact total not measured |
| Verification | Python portion installed; 75.05 MiB mixed venv with Python 3.11 and 3.15 library directories; full native profile not installed | At least 5.7 MiB of named CPython 3.11 wheels; exact total not measured |
| Formal | Plan only; full installed size not measured | No optional formal download |
| Arch | Plan only; full installed size not measured | No optional architecture download |
| All | Plan only; full installed size not measured | No all-profile download |
| Required fresh Spike | 99.61 MiB installed; 1205.21 MiB source/build tree | Git source fetched at the fixed revision; transfer bytes not measured |
| Required shim | 0.16 MiB | Locally built; no prebuilt shim download |
| Private sbt archive | 55.5 MiB archive, plus extracted launcher | 55.5 MiB archive payload |
| Private cache, later combined snapshot | 593.29 MiB | Includes Scala, Python and local run data; not a transfer total |

The verification measurement includes the base environment and retained
Python 3.15 files after migration to 3.11. It is not a standalone profile size.
Formal, arch and all were checked with installer plans only. No profile transfer
meter was used. Exact download sizes and full native profile footprints remain
unmeasured; use the inventory plans before a full installation.

## Command ledger

Times are wall seconds for each listed shell command line. A line with `&&`
contains several ordered commands and has one aggregate time. Preparation and
fix-test timings are separate. Exit codes and bounded stops are retained.
The command text uses the private `$HOME` and `$CACHE` defined above. Each
shell starts in `$CHECKOUT` and sources its env.sh when that file exists.

| # | Command | Seconds | Exit |
|---|---|---:|---:|
| clone | `gh repo clone riscPrint/risc-v-workstation "$CHECKOUT"` | 28.98 | 0 |
| 1 | `scripts/install.sh --profile minimal` | 0.62 | 1 |
| 2 | `scripts/install.sh --profile verification --dry-run` | 3.67 | 1 |
| 3 | `mkdir -p "$HOME/projects"; git clone https://github.com/SpinalHDL/VexRiscv "$HOME/projects/VexRiscv" && git -C "$HOME/projects/VexRiscv" checkout -b rvw-project baf7dc82f855eddaf5b0a20a6802c526f127e38a` | 15.44 | 0 |
| 4 | `curl -fL --retry 2 https://github.com/sbt/sbt/releases/download/v1.11.7/sbt-1.11.7.zip -o "$XDG_CACHE_HOME/sbt.zip" && unzip -q "$XDG_CACHE_HOME/sbt.zip" -d "$HOME" && ln -sf "$HOME/sbt/bin/sbt" ../bin/sbt` | 60.08 | 0 |
| 5 | `scripts/install.sh --profile verification` | 28.31 | 1 |
| 6 | `rvw/.venv/bin/rvw mcp --profile core --list` | 5.13 | 0 |
| 7 | `scripts/ci-local.sh --tier fast` | 0.66 | 127 |
| 8 | `for p in formal arch all; do scripts/install.sh --profile "$p" --dry-run > "../logs/profile-$p.log" 2>&1; printf "%s exit %s\n" "$p" "$?"; done` | 27.83 | 0 |
| 9 | `rvw/.venv/bin/rvw doctor --json` | 51.73 | 1 |
| 10 | `scripts/install.sh --profile minimal --check` | 6.20 | 1 |
| 11 | `scripts/install.sh --with-sim --with-riscv-gcc --with-cosim` | 7.10 | 2 |
| 12 | `scripts/install.sh --profile minimal && source env.sh && rvw --version` | 23.17 | 0 |
| 13 | `cd "$HOME/projects/VexRiscv" && ./rvw/build-tests.sh` | 0.44 | 1 |
| 14 | `du -sk rvw/.venv ../cache/uv; rvw doctor --json > ../logs/doctor-after-minimal.json` | 15.60 | 1 |
| 15 | `git clone --recursive https://github.com/riscv-software-src/riscv-tests "$HOME/projects/riscv-tests" && git -C "$HOME/projects/riscv-tests" rev-parse HEAD` | 19.78 | 0 |
| 16 | `git clone https://github.com/YosysHQ/picorv32 "$HOME/projects/tiny-core" && git -C "$HOME/projects/tiny-core" checkout -b rvw-project ef203c2b0a3fb793280f5114941416c425c5b461` | 2.34 | 0 |
| 17 | `cd rvw && uv sync --locked --extra dev --extra mcp && .venv/bin/python -m pytest --version && cd .. && scripts/install.sh --profile minimal && rvw/.venv/bin/python -m pytest --version` | 71.55 | 1 |
| 18 | `cd examples/vexriscv && cp rvw.toml "$HOME/projects/VexRiscv/rvw.toml" && cp -R rvw "$HOME/projects/VexRiscv/rvw" && cd "$HOME/projects/VexRiscv" && RVW_VEX_LOCK=vex-freshclone RVW_SBT_LOCK=sbt-freshclone ./rvw/run.sh build --config rv32im --rvfi --json` | 120.49 | 124 |
| 19 | `curl -I --max-time 15 https://repo1.maven.org/maven2/org/scala-sbt/sbt/1.10.7/sbt-1.10.7.pom; curl -I --max-time 15 https://repo.maven.apache.org/maven2/org/scala-sbt/sbt/1.10.7/sbt-1.10.7.pom` | 0.47 | 0 |
| 20 | `cd "$HOME/projects/tiny-core" && rvw init --isa rv32im --name tiny-core --hdl sv --top picorv32 --source picorv32.v --define RISCV_FORMAL --param PROGADDR_RESET=0x80000000 --param PROGADDR_IRQ=0x80000010 --param ENABLE_MUL=1 --param ENABLE_DIV=1 --clock clk --reset resetn --reset-active low --reset-pc 0x80000000 --accept-platform-defaults --json` | 9.45 | 0 |
| 21 | `cd "$HOME/projects/VexRiscv" && RISCV_TESTS_SOURCE="$HOME/projects/riscv-tests" ./rvw/build-tests.sh && rvw regress list --suite isa --json` | 25.75 | 2 |
| 22 | `cd "$HOME/projects/VexRiscv" && export VEXRISCV="$PWD" && rvw regress list --suite isa --json` | 3.15 | 0 |
| 23 | `cd "$HOME/projects/tiny-core" && ./rvw/build-smoke.sh && rvw regress list --json && rvw regress run --tier quick --rvfi-trace --no-index --out rvw/out/first-run --json` | 120.30 | 124 |
| 24 | `mkdir -p .tools/src/spike && git -C .tools/src/spike init && git -C .tools/src/spike remote add origin https://github.com/riscv-software-src/riscv-isa-sim.git && git -C .tools/src/spike fetch --depth 1 origin eff659cd43d7eafb7f3559bceed2540eabb31c50 && git -C .tools/src/spike checkout --detach FETCH_HEAD && mkdir .tools/src/spike/build && cd .tools/src/spike/build && ../configure --prefix="$RVW_HOME/.tools/spike" --without-boost --without-boost-asio --without-boost-regex && nice -n 10 make -j2` | 120.05 | 124 |
| 25 | `cd "$HOME/projects/VexRiscv/rvw" && "$RVW_HOME/scripts/with-lock.sh" sbt-freshclone nice -n 10 sbt -batch update db/update` | 277.98 | 0 |
| 26 | `cd "$HOME/projects/VexRiscv" && export VEXRISCV="$PWD" RVW_VEX_LOCK=vex-freshclone RVW_SBT_LOCK=sbt-freshclone && rvw regress run --suite isa --filter "^rv32ui-p-(add\|beq\|lw)$" --rvfi-trace --out rvw/out/first-isa --no-index --json` | 120.74 | 124 |
| 27 | `nice -n 10 make -C .tools/src/spike/build -j2` | 120.04 | 124 |
| 28 | `cd "$HOME/projects/VexRiscv" && RVW_VEX_LOCK=vex-freshclone RVW_SBT_LOCK=sbt-freshclone ./rvw/run.sh build --config rv32im --rvfi --json` | 120.55 | 124 |
| 29 | `nice -n 10 make -C .tools/src/spike/build -j2` | 120.05 | 124 |
| 30 | `cd rvw && uv sync --locked --extra dev --extra mcp && uv sync --locked --inexact --no-dev --extra mcp && .venv/bin/python -m pytest --version` | 1.79 | 0 |
| 31 | `nice -n 10 make -C .tools/src/spike/build -j2` | 122.08 | 124 |
| 32 | `cd "$HOME/projects/VexRiscv/rvw" && "$RVW_HOME/scripts/with-lock.sh" sbt-freshclone nice -n 10 sbt -batch -Dsbt.offline=true compile db/compile` | 231.08 | 0 |
| 33 | `nice -n 10 make -C .tools/src/spike/build -j2` | 122.08 | 124 |
| 34 | `cd "$HOME/projects/VexRiscv" && export VEXRISCV="$PWD" RVW_VEX_LOCK=vex-freshclone RVW_SBT_LOCK=sbt-freshclone && rvw regress run --suite isa --filter "^rv32ui-p-(add\|beq\|lw)$" --rvfi-trace --out rvw/out/isa-2 --no-index --json` | 122.10 | 124 |
| 35 | `nice -n 10 make -C .tools/src/spike/build -j2` | 122.09 | 124 |
| 36 | `cd "$HOME/projects/VexRiscv" && RVW_VEX_LOCK=vex-freshclone RVW_SBT_LOCK=sbt-freshclone ./rvw/run.sh build --config rv32im --rvfi --json` | 48.44 | 0 |
| 37 | `scripts/ci-local.sh --tier fast` | 685.20 | 1 |
| 38 | `nice -n 10 make -C .tools/src/spike/build -j2` | 122.06 | 124 |
| 39 | `cd "$HOME/projects/VexRiscv" && git config user.name "Fresh clone test" && git config user.email freshclone@localhost && git add rvw.toml rvw && git commit -m "test: add workstation project files" && export VEXRISCV="$PWD" RVW_VEX_LOCK=vex-freshclone RVW_SBT_LOCK=sbt-freshclone && rvw regress run --suite isa --filter "^rv32ui-p-(add\|beq\|lw)$" --rvfi-trace --out rvw/out/isa-3 --no-index --json` | 122.06 | 124 |
| 40 | `cd "$HOME/projects/VexRiscv" && export VEXRISCV="$PWD" RVW_VEX_LOCK=vex-freshclone RVW_SBT_LOCK=sbt-freshclone && rvw regress run --suite isa --filter "^rv32ui-p-(add\|beq\|lw)$" --jobs 1 --rvfi-trace --out rvw/out/isa-serial --no-index --json` | 65.41 | 0 |
| 41 | `nice -n 10 make -C .tools/src/spike/build -j2` | 94.64 | 0 |
| 42 | `scripts/install.sh --profile minimal && rvw/.venv/bin/python -m pytest --version && scripts/install.sh --with-sim --with-riscv-gcc --with-cosim` | 62.17 | 0 |
| 43 | `cd "$HOME/projects/VexRiscv" && export VEXRISCV="$PWD" && rvw cosim check --elf rvw/out/isa/rv32ui-p-add --trace rvw/out/isa-serial/isa/rv32im/tests/rv32ui-p-add/rvfi.jsonl --json` | 7.45 | 0 |
| 44 | `cd "$HOME/projects/VexRiscv" && export VEXRISCV="$PWD" RVW_SBT_LOCK=sbt-freshclone && rvw query build --config rv32im --json` | 49.27 | 0 |
| 45 | `cd "$HOME/projects/tiny-core" && git config user.name "Fresh clone test" && git config user.email freshclone@localhost && git add rvw.toml rvw && git commit -m "test: add mapped workstation project" && rvw regress run --tier quick --jobs 1 --rvfi-trace --no-index --out rvw/out/first-pass --json` | 64.96 | 0 |
| 46 | `cd "$HOME/projects/VexRiscv" && export VEXRISCV="$PWD" && rvw query where rvfi_rd_wdata --json && rvw mcp --profile core --list && rvw doctor --features sim,riscv-gcc,cosim --json > "$XDG_CACHE_HOME/doctor-vex.json"` | 31.36 | 1 |
| 47 | `for p in verification formal arch all; do scripts/install.sh --profile "$p" --dry-run > "../logs/final-profile-$p.log" 2>&1; printf "%s exit %s\n" "$p" "$?"; done; du -sk rvw/.venv .tools/spike .tools/src/spike Cosim/build "$XDG_CACHE_HOME"` | 6.13 | 0 |
| 48 | `rvw mcp --list > "$XDG_CACHE_HOME/mcp-all.txt"` | 3.63 | 0 |
| 49 | `scripts/ci-local.sh --tier fast` | 454.95 | 1 |
| 50 | `scripts/install.sh --profile verification --dry-run && scripts/install.sh --profile verification --check` | 7.67 | 1 |
| 51 | `scripts/install.sh --check --with-sim --with-riscv-gcc --with-cosim` | 8.44 | 0 |
| 52 | `cp examples/vexriscv/rvw.toml "$HOME/projects/VexRiscv/rvw.toml" && cd "$HOME/projects/VexRiscv" && unset VEXRISCV RVW_PROJECT RVW_CORE && git add rvw.toml && git commit -m "test: update workstation project defaults" && rvw regress list --suite isa --json > "$XDG_CACHE_HOME/final-isa-list.json" && rvw doctor --features sim,riscv-gcc,cosim --json > "$XDG_CACHE_HOME/final-doctor.json"` | 93.36 | 1 |
| 53 | `scripts/install.sh --with-cocotb --with-pyuvm && rvw/.venv/bin/python -c "import sys, cocotb, pyuvm; print(sys.version.split()[0], cocotb.__version__, pyuvm.__version__)"` | 11.98 | 0 |
| 54 | `cd "$HOME/projects/VexRiscv" && unset VEXRISCV && rvw cosim check --elf rvw/out/isa/rv32ui-p-add --trace rvw/out/isa-serial/isa/rv32im/tests/rv32ui-p-add/rvfi.jsonl --json > "$XDG_CACHE_HOME/cosim-py311.json"` | 10.95 | 0 |
| 55 | `scripts/install.sh --profile minimal && rvw/.venv/bin/python -c "import cocotb, pyuvm, pytest; print(cocotb.__version__, pyuvm.__version__, pytest.__version__)" && rvw mcp --profile core --list > "$XDG_CACHE_HOME/mcp-py311.txt" && du -sk rvw/.venv && scripts/install.sh --profile verification --check` | 12.42 | 1 |
| 56 | `scripts/install.sh --with-cocotb --with-pyuvm && scripts/install.sh --profile minimal && rvw/.venv/bin/python -c "import sys, cocotb, pyuvm, pytest; print(sys.version.split()[0], cocotb.__version__, pyuvm.__version__, pytest.__version__)" && rvw mcp --profile core --list > "$XDG_CACHE_HOME/mcp-stable-py311.txt" && du -sk rvw/.venv` | 1.19 | 2 |
| 57 | `scripts/install.sh --with-cocotb --with-pyuvm && scripts/install.sh --profile minimal && rvw/.venv/bin/python -c "import sys, cocotb, pyuvm, pytest; assert sys.version_info[:2] == (3, 11); print(\"STABLE_PYTHON\", sys.version.split()[0], cocotb.__version__, pyuvm.__version__, pytest.__version__)" && rvw mcp --profile core --list > "$XDG_CACHE_HOME/mcp-stable-py311.txt" 2> "$XDG_CACHE_HOME/mcp-stable-py311.err" && du -sk rvw/.venv` | 11.07 | 0 |
| 58 | `Cosim/build.sh && cd "$HOME/projects/VexRiscv" && unset VEXRISCV && python3 -c "import sys; assert sys.version_info[:2] == (3, 11); print(sys.version.split()[0])" && rvw cosim check --elf rvw/out/isa/rv32ui-p-add --trace rvw/out/isa-serial/isa/rv32im/tests/rv32ui-p-add/rvfi.jsonl --json > "$XDG_CACHE_HOME/cosim-stable-py311.json"` | 21.66 | 0 |
| 59 | `scripts/install.sh --profile verification --check; result=$?; du -sk rvw/.venv "$XDG_CACHE_HOME"; exit "$result"` | 19.48 | 1 |
| 60 | `git rev-parse HEAD && scripts/ci-local.sh --tier fast` | 657.79 | 2 |
| 61 | `rvw mcp --profile core --list > "$XDG_CACHE_HOME/mcp-latest.txt" 2> "$XDG_CACHE_HOME/mcp-latest.err"` | 1.07 | 0 |
| 62 | `git rev-parse HEAD && scripts/ci-local.sh --tier fast` | 798.19 | 1 |
| 63 | `git pull --ff-only && git rev-parse HEAD && rvw/.venv/bin/python -m pytest rvw/tests/test_agent_ooo_pack.py -q && rvw mcp --profile core --list > "$XDG_CACHE_HOME/mcp-final.txt" 2> "$XDG_CACHE_HOME/mcp-final.err" && ! rg -i skipped "$XDG_CACHE_HOME/mcp-final.err"` | 0.75 | 1 |
| 64 | `git -C "$CHECKOUT" pull --ff-only` | 1.64 | 0 |
| 65 | `git rev-parse HEAD && rvw/.venv/bin/python -m pytest rvw/tests/test_agent_ooo_pack.py -q && rvw mcp --profile core --list > "$XDG_CACHE_HOME/mcp-final.txt" 2> "$XDG_CACHE_HOME/mcp-final.err" && python3 -c "from pathlib import Path; import os; assert \"skipped\" not in Path(os.environ[\"XDG_CACHE_HOME\"], \"mcp-final.err\").read_text().lower()"` | 1.98 | 0 |
| 66 | `git rev-parse HEAD && scripts/ci-local.sh --tier fast` | 430.78 | 1 |

## Linux differences

Linux was NOT RUN. Debian/Ubuntu use apt recipes; Fedora/RHEL use dnf recipes.
Package names, shared-library loading, compiler tools and RISC-V GCC locations
can differ. Python wheels and native archives also differ by platform. Homebrew paths do not apply. Use the inventory plans for the host.
Java 21 and the matching Spike source/header/library requirements still apply.
An existing Linux sbt cache is not a substitute for the documented fresh fetch.
No Linux time, download size, native pass, or install qualification is claimed.

## Retained limits and cleanup

An earlier complete clean CI run used workstation `9c0838ca` and Python
3.11.18. Pytest ran at nice 10. It reported 3307 passed, 4 skipped and 2 failed
in 715.20 seconds. The whole CI command took 798.19 seconds and exited 1.
The summary measured 713.89 seconds against a target below 300 seconds. That
run did not meet the fast-tier time target.

The failures were:

- `test_agent_ooo_pack.py::test_pinned_ooo_mutations_round_trip`: the isolated
  CI repository has no historical source commit. [#1418](https://github.com/riscPrint/risc-v-workstation/pull/1418) supplies the exact
  pinned source as a fixture and validates its pin and SHA-256. All ten mutation
  round trips passed in a copied test tree with no Git metadata. This is a test
  dependency fix, not native OoO core qualification.
- `test_mcp_workflow_coverage.py::test_each_tool_has_a_profile_and_workflow`:
  `cov_mutate_core` had no workflow entry at that revision. This untouched
  coverage metadata failure belongs to the coverage area. It was not waived.

The initial post-pull check used the targeted fixture test and core MCP list.
After a pull to `85df0791`, the fixture test passed in 0.27 seconds and the
core MCP list had no skipped-module warning. The combined command took
1.98 seconds. A later full clean CI repeat is recorded below.

The early complete clean CI run had 3042 passes, 4 skips and one VHDL
launcher failure. A later Python 3.15 run had 3085 passes, 4 skips and no test
failures in 410.10 seconds, but exceeded its 300-second target. Both used the
unintended effective nice 20. An intermediate Python 3.11 run was stopped when
this priority error was found: 1480 passed, 3 skipped and two failures were
reported before interruption. It is incomplete evidence. Those failures were
stale generated agent-guide text and an unregistered workflow for
agent_bench_evidence_solve. Later main updates changed these metadata findings.

The installer-fix worktree fast set had 3238 passes, 4 skips and one untouched
workflow-coverage failure for agent_bench_evidence_solve in 631.18 seconds.
The documentation check at a later main revision found cov_mutate_core missing
from workflow coverage instead. These are recorded snapshots of moving main;
no check was skipped, waived or weakened to obtain a pass. They are outside
installer repair. The later clean result below states the final findings.

The compatible Python install passed with cocotb 2.1.0 and pyuvm 4.0.1 on
Python 3.11.18. Repeating minimal kept that interpreter and those imports,
including pytest 9.2.0. A stale venv alias and uv's unversioned interpreter
selection had each broken this sequence before the last two installer fixes.
The versioned interpreter was selected by validated absolute path. No Python
runtime was downloaded for this selection.

The final verification check reported cocotb and pyuvm installed and all
requested simulation, GCC and Spike prerequisites present. It exited 1 for
uninstalled Verible and riscv-dv, which were deliberately not downloaded.
No full verification-profile install or native cocotb simulation is claimed.
The old uv-version hint was not reproduced: uv 0.13.6 met the requirement.

The complete add trace also matched Spike after rebuilding the shim and
checking the stable Python 3.11 interpreter. It retained 504 instructions,
4 traps, trace_complete=true, end_status=pass and one declared CSR reset sync.
The core MCP list included regress_list and cosim_check without a skipped
module warning. Listing is not an MCP transport or native-tool qualification.

After the example fixes were pulled, the copied project listed 49 ISA tests
with VEXRISCV unset. Doctor marked project and adapter.info ready. It retained
adapter.build_run=inconclusive because no doctor smoke was requested. The
separate regress records establish the stated C1 runs only. Unbuilt dv-baseline
and act4 suites remain errors. Doctor ELF-presence checks do not establish
runtime results for the cached, debug or Linux configurations.

The fixture-fix fast set before the next main update had 3308 passed, 4 skipped and one workflow failure
for cov_mutate_core in 408.24 seconds. The staged release checks had 40 passes
in 44.48 seconds. The mutation fixture and release checks together had 41
passes. A separate tree with no Git metadata passed all ten mutation round
trips through its one test in 0.54 seconds.

The report-worktree fast set at `88abf841` had 3485 passed, 4 skipped and
7741 deselected in 270.16 seconds. The report and guide checks had 47 passed
and 30 warnings in 43.37 seconds. Main's workflow update was included in this
snapshot. The earlier missing workflow entry was therefore no longer a test
failure. This direct worktree run did not replace the isolated CI tier.

The final complete isolated CI repeat used workstation `85df0791` and Python
3.11.18 at nice 10. It reported **3498 passed, 4 skipped, 0 failed and 0 errors**.
Pytest took 397.92 seconds. The JUnit summary measured 397.69 seconds, above
the unchanged 300-second target. The whole command took 430.78 seconds and
exited 1 because of that time target. No functional test failure remained in
this snapshot. The fast CI tier is therefore not a passing gate result.

The four skips were two raw activation-evidence checks, one raw native VIP
matrix check, and the command-reference check deferred by the owner during
the parallel push. These skips do not qualify the omitted native campaigns.
The direct worktree and isolated runs used different source snapshots and
environments on a shared host. Their times are not a paired performance test.

No full Python suite, BOOM build, long formal run, native VHDL campaign,
full optional native-tool campaign or Linux-host qualification was run.

All raw logs, caches, native builds, copied cores and trace data belonged to
`$RUN_ROOT`. They are not committed with this report. Remove the disposable trial
root after the final checks. This report retains only the commands,
counts, timings, source pins and fix links needed to repeat the trial.
