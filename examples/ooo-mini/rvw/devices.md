# Device and live comparison checks

The adapter routes CLINT and PLIC accesses through the standard device plugins.
The project files declare the address windows and interrupt routes. Each run
creates fresh devices. RAM still has no wait state.

A device load issues only at the ROB head. An accepted device load retires before
an interrupt can discard it. Other valid heads can take an interrupt before
execution finishes. This lets interrupt recovery cancel a pending divide.
The core suppresses load requests for illegal encodings. Stores reach devices
only at commit. These rules keep wrong-path and illegal PLIC reads from consuming
a claim. Default dimensions and the Core and MulDiv module names stay unchanged.

## Measured results

Default configuration, seed 17, 25 native monitors and eight generated SV binds:

| Program or campaign | RTL result | Cycles | Retirements | Spike result |
|---|---|---:|---:|---|
| Generated CLINT software WFI, MIE clear | Pass | 72 | 48 | Match, one IRQ synchronization |
| Generated CLINT software WFI, MIE set | Pass | 82 | 57 | Match, zero synchronization |
| Generated CLINT timer WFI, MIE clear | Pass | 170 | 124 | Match, three MMIO and one IRQ synchronization |
| Generated CLINT timer WFI, MIE set | Pass | 180 | 134 | Match, three MMIO synchronizations |
| Directed PLIC, offline | Pass | 150 | 79 | Complete strict match, 80 instruction records, zero synchronization |
| Directed PLIC, socket lockstep | Pass | 150 | 79 | Complete strict match, 80 instruction records, zero synchronization |
| Base regression after device changes | 307/307 pass | Per-program reports | Per-program reports | 304 strict matches; three masked-WFI matches with one IRQ synchronization each |
| M-to-U PMP isolation pair after device changes | Complete, no_leak_observed | Two public windows of 21 cycles | Two fresh runs | One secret pair only |

All positive runs have zero native monitor firings. The default SV binds run
with Verilator assertions enabled. The live C1 report confirms socket lockstep.
The PLIC evidence checker independently accepts five pin events, five accepted
MMIO events, one interrupt taken, one claim and one completion. The program checks
vectored MEIP delivery, mepc, mcause, zero mtval, MIE/MPIE and MRET. It also executes
an illegal RV32 LD and a wrong-path LW at the claim address. Neither consumes a
claim. The held-high source is disabled by the handler after completion.

CLINT time reads use explicit MMIO synchronization. Masked pending-pin reads
use explicit IRQ synchronization. These are not strict matches. No counter or
other CSR synchronization is enabled. WFI is a permitted early-return hint;
clock stopping is not tested.

The base regression qualifies the three directed probe plans again. The
full-ROB software interrupt case now takes 112 cycles and 48 retirements. The
speculative-fault case takes 165 cycles and 80 retirements. The forwarding and
recovery case takes 307 cycles and 112 retirements. All declared positive bins
hit. Consecutive-cycle recovery remains unhit.

## Negative controls

Two separate source mutations run the same PLIC program with a 1,000-cycle limit.
The good source is restored after each mutation. Neither negative run is included
in the positive monitor count.

| Mutation | Result | Native monitor result |
|---|---|---|
| Replace mmioBlocked with False | Timeout, 944 retirements | mmio_at_head fires once, at cycle 52 |
| Remove !exception from the io.load condition | Timeout, 943 retirements | Zero firings; the self-checking program detects the lost interrupt |

Both mutations consume the PLIC claim before the handler. The controls show why
both the monitor and the self-checking program are needed. They do not establish
complete monitor fault coverage.

## Reproduce

Use the native environment and RISC-V GCC. Run from the workstation checkout.
Use a fresh output path. The script builds the device library unless --library
names an existing library.

```sh
export RVW_HOME="$PWD"
export RVW_SBT_LOCK=sbt-ooomini2
export RVW_OOO_LOCK=ooo-mini-ooomini2
nice -n 10 rvw/.venv/bin/python examples/ooo-mini/rvw/check-devices.py \
  --out examples/ooo-mini/rvw/out/device-check
```

The script saves the two `rvw regress plan` selections. The CLINT profile selects
the RV32 CLINT WFI family. The catalog PLIC families require RV64, so this RV32
project uses the directed program. It emits the shared
rvw.external-interrupts/1 format. The generic held-source support is in
[PR #1373](https://github.com/riscPrint/risc-v-workstation/pull/1373).
Dynamic source mailboxes, multiple PLICs, reset during a pending claim and
supervisor delivery remain open. Device-library input closure is not qualified
for C4 reuse. Prior coverage and formal snapshots have different RTL identities.

Raw outputs remain in the ignored rvw/out tree. To repeat the base campaign,
use check-probes.py after its coverage prerequisites. To repeat isolation, use
the commands in protection.md with fresh output paths and regenerated RTL.
