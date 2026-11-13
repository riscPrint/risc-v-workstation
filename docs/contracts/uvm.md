# UVM flow contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## UVM register sequence diagnostics

The generated `rvw.soc/1` register model can use `rvw_ral_pkg` normalized
transfers. A transfer starts with `UVM_NOT_OK`. The project bus driver must
set completion status. An explicit predictor consumes bus observations;
auto-prediction must be disabled when that predictor is connected.
`UNSUPPORTED_RAL_BACKDOOR` refuses standard access tests without a configured
backdoor. The caller resets hardware before the standard reset sequence.
This register fixture evidence does not establish peripheral or CPU behavior.

## Live scalar UVM CPU observations

`Uvm/cpu/rvw_cpu_if.sv` carries one scalar retirement per cycle. Its 19 values
use the captured UVM replay field order. `rvfi_order` must start at zero and
increase without gaps. The live subscriber steps a separately initialized
Spike instance once per retirement. The bridge requires shim ABI 6 and the
platform PMP granularity. Missing or inconsistent observations cannot count
as checked retirements. The bounded ADDI fixture writes C1/C3 with incomplete
source identity; it does not earn C4 acceptance.

`rvw regress uvm --require-feature` checks the runner profile before tool
startup. Unqualified requirements have `unsupported:uvm_*` diagnostics and
named workarounds in `Uvm/FEATURES.md`. Unknown names are refused. These
profile limits do not claim universal simulator language limitations.

## UVM bench manifests and results

`rvw.uvm/1` declares `name`, `top`, ordered `sources` and unique `tests`.
Optional `include_dirs`, `defines`, `build_args` and `plusargs` are string
lists. Paths are relative to the manifest. Optional `register_map` names an
`rvw.soc/1` map. Optional `bindings` is an object owned by the project bench.
The flow does not translate it to signal wiring. Accellera UVM is pinned by
archive and licence hashes. `build.json` uses `rvw.uvm-build/1` and records
resolved manifest data, commands, input hashes and binary hash.

`rvw uvm run` writes C1 with `details.mode: uvm-bench`, null cycle and retirement
counts, and no ELF claim. A pass requires exit zero, no UVM error/fatal, and one
`RVW_UVM_DONE TEST checks=N` line with the selected test and positive N.
`rvw uvm regress` writes one C3 row per test/seed and links the corresponding
C1 and log. `source.identity_complete` is false. These results are component
checks, not a core gate identity. Native coverage merging does not merge
functional coverage plans or establish closure.

## UVM CPU capture replay in C3

`rvw regress uvm-cpu` consumes a completed C1 run and its C2 artifact. It
can also launch a selected adapter with `run --rvfi-trace` before replay.
It checks the C1 ELF SHA-256, status and retirement count before replay. It
requires complete, passing, contiguous scalar C2 version 1 evidence. A
UVM analysis subscriber checks each retirement with a native Spike DPI bridge.
The standalone C3 report marks `mode=offline-c1-replay` and records the
profile, captured reference inputs, source hashes, commands and logs. It
does not modify C1 or establish C4 acceptance. Unsupported profiles and
incomplete observations are errors. Source identity remains incomplete.

## SoC bus-master profile

`SocEnvironment` keeps CPU evidence required by default. A project can select
`cpu_required=False` for a bus-master bench. That profile accepts only
`finish(0)` and emits `cpu_checks=0`. Bus and UART checks remain required.
It must not be presented as CPU execution evidence.

## Database-selected bench profile scaffolds

`uvm new` accepts `language=pyuvm|sv` and a database bus `profile`.
Auto selection requires one recognized top-level bus. Output includes its
port inventory, clock domains and project scenario hook. Profile generation
is structural evidence only. Unbound and empty scenarios must fail. The
default single-APB pyuvm path retains its automatic reset-read bench.
