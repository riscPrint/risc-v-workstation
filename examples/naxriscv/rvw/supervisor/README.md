# RV64 supervisor campaign

Use the extra `rv64imasu` config. The base project keeps its RV32 default.
The core pin and setup are in the [example README](../../README.md).
The adapter reads the core. It does not change upstream source.

| Selection | Result |
|---|---|
| `rvw regress plan` | 8 of 13 families apply |
| Sv39 base matrix | 135 of 147 Sv39 rows selected |
| Excluded matrix rows | 2 need PMP, 2 need hardware A/D updates, 8 need ASIDs |
| Other excluded families | PMP, AMO protection faults, two-hart shootdown, H, Svnapot/Svpbmt |
| Privilege controls / seeded transitions / scheduled WFI | 30 / 4 / 6 programs |
| LR/SC / AMO / fence / fence.i | One seeded program each |

The project catalog removes the PMP requirement only from families whose
bootstrap supports zero PMP entries. It keeps their access and trap checks.
The configuration has no PMP regions. It has one hart, ASIDLEN zero and
software-managed A/D bits. A declared capability selects tests. It does not
prove that the core implements that capability correctly.

Run from the workstation checkout. Set up the private core, Python environment,
RISC-V GCC and Spike shim as described in the example README. `NAX_SUITES_OUT`
and `RUN_ROOT` must be outside Git. `prepare.py` requires a new output path.

```sh
export RVW_NAX_LOCK=nax-nax64 RVW_NAX_SBT_LOCK=sbt-nax64
export NAX_SUITES_OUT="$RUN_ROOT/supervisor-suites"
rvw regress plan --features examples/naxriscv/rvw/supervisor/features.json \
  --catalog examples/naxriscv/rvw/supervisor/catalog.json --json
nice -n 10 python examples/naxriscv/rvw/supervisor/prepare.py \
  --out "$NAX_SUITES_OUT"
rvw --project examples/naxriscv checks generate --all --out "$RUN_ROOT/checks64" --json
export RVW_NAX_CHECKS="$RUN_ROOT/checks64/queues"
nice -n 10 rvw --project examples/naxriscv/rvw64.toml regress run \
  --suite mmu,privilege,random-privilege,ordering,scheduled-wfi-3-0,scheduled-wfi-3-1,scheduled-wfi-7-0,scheduled-wfi-7-1,scheduled-wfi-11-0,scheduled-wfi-11-1 \
  --source "$NAXRISCV" --rvfi-trace --jobs 4 --no-index \
  --out "$RUN_ROOT/supervisor"
nice -n 10 rvw regress cosim "$RUN_ROOT/supervisor" \
  --platform examples/naxriscv/rvw/platform-rv64imasu.json \
  --out "$RUN_ROOT/supervisor-cosim.json" --json
rvw regress mmu report "$NAX_SUITES_OUT/mmu" \
  --results "$RUN_ROOT/supervisor" --json
```

Probes retain the instruction and privilege at ROB allocation. The C2 memory
address comes from the LSU virtual-address stage. The architectural memory
image and tohost use the observed physical address. This supports translated
fetch and data paths without an instruction lookup at a virtual ELF address.
The adapter drives scheduled interrupt pins and records their input levels.

`mmu-observations.jsonl` records the MMU cache-load port's requests, responses
and retries. It also records accepted native data-cache refill reads. The
bounded checker compares immutable preset-A/D load/store walks with the
declared page tables. Fetch, fault, remap and other unsupported paths stay
inconclusive in that checker. Raw page-walk events remain available. This
check is separate from strict architectural comparison. It does not prove
TLB protocol behavior or instruction/data coherence.

The pinned core exposes MEDELEG bits 0, 3, 8, 9, 12, 13 and 15. Illegal
instruction delegation is read-only zero. The seeded generator uses that
declaration. It still tests illegal instructions with M-mode trap delivery.
The adapter samples the privileged unit's trap EPC. A decode-time trap need
not have the last retired instruction's ROB PC.

## Native results on 2026-11-13

Counts are programs. Seed 1 and zero added memory wait apply to each RTL run.
The final fetch and seeded runs use the corrected trap-EPC observer.

| Family | Selected | C1 pass | C1 fail | Complete strict Spike match | IRQ-synchronized match |
|---|---:|---:|---:|---:|---:|
| Sv39 translation | 135 | 119 | 16 | 119 | 0 |
| TVM / TW / TSR controls | 30 | 30 | 0 | 30 | 0 |
| Seeded trap, delegation and return | 4 | 4 | 0 | 4 | 0 |
| LR/SC | 1 | 1 | 0 | 1 | 0 |
| AMO | 1 | 1 | 0 | 1 | 0 |
| Fence | 1 | 1 | 0 | 1 | 0 |
| Fence.i | 1 | 1 | 0 | 1 | 0 |
| Scheduled MSIP / MTIP / MEIP | 6 | 6 | 0 | 0 | 6 |
| Protection regions | 0 | 0 | 0 | 0 | 0 |

All 16 failing MMU programs were also compared directly with strict Spike.
All 16 differ at a missing page fault. Fourteen concern MPRV permissions.
Two concern noncanonical addresses. See [the findings](../../FINDINGS.md).
The strict WFI comparisons differ at the corresponding MIP input bit.
There is no output mask. Counter, MMIO and CSR synchronization remain disabled.
The six IRQ comparisons need the explicit `--allow-sync irq` policy.

| Page-walk observation | Result |
|---|---:|
| Bound MMU observation files | 135 |
| Returned PTE observations | 442 |
| Bounded immutable load/store walks consistent | 26 |
| Other bounded walk checks | 109 inconclusive |
| Bounded walk mismatches after scope correction | 0 |

The report above is an observation inventory. Architecture bin coverage was
not derived from it. The architectural counts come from C1 plus strict
retirement comparison. The full 142-bin MMU coverage report without a
`--checked` oracle remains inconclusive.

Raw data stays outside Git. The first complete campaign and the final
40-fetch/4-seed/6-WFI rerun retain their own ELF receipts. A fresh build has
different nonloaded ELF metadata. All 135 MMU load segments, entry points,
XLEN values and tohost addresses match the original corpus exactly.
The original executed hashes remain the native evidence.

The default global catalog selects five of 37 families on the same features.
The project catalog includes those five. It adds three base families whose
shared bootstrap now supports zero PMP entries. The four seeded programs
check 128 transitions, including 11 delegated traps. Each WFI comparison
uses one IRQ synchronization. Its interrupt TVAL is the observed CSR write,
which is zero. The upstream observer's intermediate instruction value is
not the architectural TVAL.
