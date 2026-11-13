# Component simulations contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Native branch component reports

`ComponentSims/` defines `rvw.branch-trace/1`. The first line is schema plus
positive total instruction count. Each following `B ORDINAL PC TAKEN` row gives
a conditional branch, its one-based all-instruction ordinal, hexadecimal PC and
0/1 outcome. Ordinals strictly increase and cannot exceed the total. A final
`END` line is mandatory. No lines follow it. Nonbranches are represented by gaps.

The native engine emits `rvw.branch-sim/1` with `status=reported`, `model`,
`entries`, `history_bits`, `pc_shift`, `warmup_instructions`, `instructions`,
`branches`, `direction_misses`, `mpki`, `oracle_mpki=0`,
`training=sequential-actual-path`, and `rtl_comparison=inconclusive`.
`instructions` excludes warmup. `mpki` is 1000 times measured direction misses
divided by measured instructions. No C1 pass or C4 verdict is issued. Exit 0
means report completion; exit 2 means error without a stdout report.

The standalone Spike adapter selects one successful traced row from
`rvw.workload-verify/1`. It checks the retained stderr hash and instruction count.
It rejects multi-hart logs, exceptions and ambiguous branch successors.
Its `rvw.branch-sim/1` report adds `workload`, `elf_sha256`, `scope`, `oracle`,
`verify`, `source`, `trace`, `engine`, and `adapter_sha256`. The four file objects
contain absolute `path` and `sha256`. Scope includes startup and checker code.
A supplied verification report remains local trusted evidence, not an immutable
C8 generation. The adapter does not independently rerun workload correctness.
### Component study formats (`rvw csim`)

`rvw.csim-trace/1` is the native component trace. The first line is the schema.
Lines that start with `#` are comments. Rows use hexadecimal PCs, addresses and
values and decimal one-based instruction ordinals. Ordinals do not decrease;
two `B` rows cannot share one ordinal. The last line is `END INSTRUCTIONS`,
the total count of instructions, with no data after it.

```text
B ORD PC KIND TAKEN TARGET [LEN]   KIND cond|jump|ijump|call|icall|ret; TARGET is the next PC when taken
L ORD PC ADDR SIZE                 load, SIZE bytes (1..64)
S ORD PC ADDR SIZE                 store
W ORD PC RD VALUE FLAGS            register write; FLAGS '-' or letters l (load), m (move), z (zero idiom)
X ORD CONTEXT                      context (privilege mode or address space) from this ordinal on
```

Converters write an `X` row at the first instruction and at each change of the
C2 `mode` or the Spike privilege digit.

Unconditional kinds must be taken. `LEN` is 2 or 4 for RISC-V; 0 means unknown.
`rvw csim convert c2` writes it from one-hart C2 traces without order gaps. A
trapped instruction counts as an instruction but gets no branch row.
`rvw csim convert spike` reads one-hart Spike `-l --log-commits` logs: each
commit line is one instruction; a branch followed by an exception line gets no
row, and access sizes come from the decoded mnemonic.

`rvw.csim-study/1` is a JSON object with the sections `branch`, `btb`, `ras`,
`indirect`, `wrong_path`, `frontend`, `memory`, `mdp`, `vp`, `lap`, `report`, the
integers `warmup_instructions` and `simulation_instructions`, and the metadata
`name`, `description` and `source`. `source.fidelity` is `approximate` or
`unqualified`. The engine refuses unknown keys. `rvw csim models` lists the keys.

The engine writes `rvw.csim-report/1` per trace with `status=reported`, `trace`
(format, instructions, warmup, measured instructions), one object per component,
`storage` (bits per table, `total_kib`, `metadata_kib`, `cache_data_kib`),
`training=sequential-actual-path`, `rtl_comparison=inconclusive` and `limits`.
MPKI is 1000 times events over measured instructions. `rvw csim run` wraps the
reports in `rvw.csim-study-report/1` with the study hash, input hashes, engine
identity and an aggregate that names its weighting. `rvw csim sweep` writes
`rvw.csim-sweep/1`; `rvw csim budget` writes `rvw.csim-budget/1`. No report
gives a C1 pass or a C4 verdict. Exit 0 means a report; exit 2 an error.

`rvw.bp-events/1` is JSONL from a project probe binding. The header has
`schema`, `elf_sha256`, `hart`, `counter_semantics` (`first-prediction` or
`final-prediction`) and an optional `roi` (`start_order`, `end_order`). Each row
has the C2 `order` of a retired branch, `pc`, `kind`, `taken`, and optionally
`predicted_taken`, `target` and `predicted_target`. Events for squashed
instructions have no order and are refused. `rvw csim compare-rtl` writes
`rvw.csim-rtl-compare/1` with status `compared` or `inconclusive`, `reasons`,
observed direction and target counts, per-branch rows and, for Kanata input, a
separate `inferred` section.

`skip_instructions` (not above `warmup_instructions`) skips rows without any
state change. `rvw csim simpoint` writes `rvw.csim-simpoints/1`: trace path and
hash, `interval`, `intervals`, `instructions`, chosen `k`, `bic`, `dims`,
`seed` and `points` (`interval`, `start_instruction`, `instructions`, `weight`,
`members`); weights are cluster instruction shares and sum to 1.
`rvw csim run-points` writes `rvw.csim-simpoint-report/1` with each point's
report and metrics, the `weighted` metrics and the weighting statement.

`rvw csim compare BASE CANDIDATE` writes `rvw.csim-compare/1`: per trace (paired
by input sha256, else path) each shared metric's base and candidate values,
change, relative change and `better`, `worse` or `same` (within `tolerance`).
MPKI, PKI, storage and false dependences are lower-is-better; the others are
higher-is-better. Unpaired traces are counted, not compared.

`rvw csim qualify` writes `rvw.csim-qualify/1`: `status=reported`, the
reference name, URL, pinned `reference_sha256` and `reference_patch`, the study
hash, the tolerance and, per trace, input hash, conditional branch count,
reference and model misses and MPKI, `prediction_agreement`,
`within_tolerance` and the largest per-branch differences. It is a measured gap
on the given traces, not a fidelity verdict.

The comparison status is `inconclusive` when the ELF identity,
hart, counter semantics or an event for a conditional branch in the ROI is
missing, or when an event does not align with the trace. It never reports a match.
