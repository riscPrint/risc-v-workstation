# Directed Sv39 example

Use the native cross compiler and Spike. Run from the workstation root:

```sh
rvw regress mmu build examples/boom/mmu/scenarios.json --out /tmp/mmu-elfs --json
rvw regress mmu reference /tmp/mmu-elfs --timeout 10 --json
RVW_MMU_ELFS=/tmp/mmu-elfs rvw regress run --core boom --suite mmu-priv --jobs 1 --max-cycles 30000 --timeout 120 --rvfi-trace --no-cache --out /tmp/mmu-rtl --json
rvw regress mmu check /tmp/mmu-elfs --results /tmp/mmu-rtl --platform rvw/src/rvw/cosim/configs/boom.json --model spike --json
```

`--out` for build must be empty. Hold the BOOM lock for direct adapter runs.
`rvw regress run` holds it itself. Limit the whole command with a process-group
timeout if the shared machine is busy. A lock wait gives no RTL evidence.

`scenarios.json` selects Svade for A/D faults. `hardware-ad.json` is a separate
Svadu reference campaign. Do not merge those policies into one RTL suite unless
the core supports changing that policy. The generator is generic. This directory
holds BOOM's selected scenarios. Other S-mode projects can supply their own
JSON and an `elf-dir` suite. See the [regress README](../../../rvw/src/rvw/regress/README.md)
for requirements, PMA declarations, oracle checks and limits.

The known BOOM ACT4 Sv39 exception failures remain open. These directed tests
do not waive them. A Spike self-check pass is reference evidence only. It does
not establish a BOOM result or page-walk bus coverage.

The expanded suite includes actual S/U transitions for TVM, TW and TSR,
ASID reuse, an ASID-zero register operand, legal unfenced alternatives,
misaligned loads/stores, PMP denial of page-table reads and a translated CLINT
MSIP read. The CLINT read expects the harness reset value of zero. It does not
check interrupt delivery or write side effects. Sv48 is not selected because
`../soc.json` declares `Sv48.supported = false`.

Keep generated coverage outside the repository:

```sh
rvw regress mmu check /tmp/mmu-elfs --results /tmp/mmu-rtl --platform rvw/src/rvw/cosim/configs/boom.json --json > /tmp/mmu-check.json
rvw regress mmu report /tmp/mmu-elfs --results /tmp/mmu-rtl --checked /tmp/mmu-check.json --json > /tmp/mmu-coverage.json
```

BOOM captures PTW/cache requests and responses plus physical TileLink A
handshakes when RVFI tracing is enabled. The report inventories the capture
separately. A/D atomicity, concurrent PTE changes, cross-hart shootdowns, full
PMA boundary/width/atomic behavior and independent device-state checks remain
open. A PMP access-fault test does not verify PMA attributes.

The added fetch cases enter real S/U privilege with Sv39 enabled. Root-switch
cases select distinct page tables with one ASID. Non-leaf global mappings use
all-ASID fences. The TW-clear case supplies pending delegated SSIP with global
interrupts disabled. The software RSW cases check the whole final PTE; their
software write is sequential, not a concurrent page-table race.

Use `--pma examples/boom/mmu/pma.json` on `mmu build` to retain the focused RAM
and MSIP declarations. This file does not describe every device. The MSIP
store uses the legal value 1 and a 4-byte access. The report compares accepted
transfers with independent harness MSIP state. Missing capture remains
inconclusive. PMA boundary fault and conflicting-attribute campaigns remain open.
