# Native component simulators

This tool studies conditional branch direction on actual-path traces.
It has bimodal, gshare and perfect-direction models. It does not model cycles.
See [the design](../docs/design/component-sims.md) for phases and contracts.

## Build and use

Build with a native C++17 compiler. No libraries or downloads are needed.

```sh
c++ -std=c++17 -O2 -Wall -Wextra -Werror ComponentSims/branch_sim.cc -o /tmp/branch-sim
/tmp/branch-sim gshare 4096 12 1 0 < trace.txt
```

Arguments are model, power-of-two table entries, history bits (0-63), PC shift
(0-63), and warmup instruction count. Defaults are bimodal, 4096, 12, 1, 0.
Counters start weakly not taken. History starts at zero and includes only
conditional outcomes. Prediction precedes training. Each process starts fresh.

Trace format:

```text
rvw.branch-trace/1 10
B 2 80000000 1
B 6 80000004 0
END
```

The header counts all instructions, including nonbranches. Branch rows contain
one-based instruction ordinal, hexadecimal PC and direction (0 or 1). Ordinals
must increase. `END` must be the last line. Warmup trains state but excludes
instructions and misses through the selected ordinal. Empty measured intervals
are errors. Zero-branch intervals are valid. Exit 0 means a report was produced.
Exit 2 means an error; stdout then has no report.

## Decisions and limits

The engine is owner-written C++ with no copied third-party source. The project
license choice remains in #37. It does not import ChampSim or competition code.

Reports give per-trace instruction counts, direction misses and MPKI. The perfect
direction bound is zero misses because it reads actual outcomes. It is not an
IPC or speedup bound. The native text input is caller-declared evidence. The
Spike adapter adds source hashes. Neither flow claims complete C8 capture.

Sequential actual-path training has no speculation, wrong-path work or delayed
updates. TAGE-SC-L, BOOM-like settings, BTB/RAS, memory models, RTL comparisons,
CLI/MCP bindings and public trace qualification are not implemented.

Run targeted checks with `python -m pytest ComponentSims/tests -q`.

## Spike workload input

First run `rvw workloads verify --trace` with Spike. Select one successful row:

```sh
python3 ComponentSims/spike.py --verify /path/to/reference/verify.json \
  --workload crc32 --engine /tmp/branch-sim --out /path/to/study \
  --model gshare --entries 4096 --history 12 --pc-shift 1 --warmup 0
```

Use a new output directory for each workload/model. The adapter writes trace.txt
and report.json. It checks the verification status, Spike identity, retained log
hash and instruction count. It binds the report, log, trace, engine and adapter
hashes. It checks standard and compressed conditional targets against the next
logged PC. It refuses multiple harts, exceptions, unresolved final branches and
cases where target equals fallthrough. A refused run can leave a trace directory
without report.json. Use another output directory after correction.

Counts cover the full log, including startup and checker code. Test fixtures
validate conversion and native execution. They do not qualify a published CBP
trace set or a real application measurement. No RTL model is built by this tool.
