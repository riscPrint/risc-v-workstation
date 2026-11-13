# Bundled BOOM ACT4 profile

This is the same `rvw.act4/1` suite description used by external core
projects. The bundled `rvw/configs/boom.toml` selects its manifest-bound
ELFs as `act4-project`. The legacy `act4` suite stays available.

The profile uses RV64IMAFDC, Zba/Zbb/Zbs, Zicsr/Zifencei and Zicntr/Zihpm.
This is the ISA in the bundled comparison platform's `reference_isa`.
It declares M/S/U, Sv39, 32 physical address bits, eight usable PMP entries
and the BOOM harness memory map. The trace ISA omits the reference-only
Zicntr/Zihpm labels. The comparison platform has no CSR output masks.

The UDB parameters, model macros and map come from the existing BOOM port
flow at `spinal-boom/act4/boom-rv64gc`. `source.json` records the input
file hashes and changes. Extra hint and Zicc property extensions in that
legacy flow are outside this selection. The local Sail configuration
disables those extra instruction features. The linker adds actual reset
instructions to clear mscratch and mtvec before the standard bootstrap.
The Sail IO regions and CLINT size match the bundled platform map.
The standard bootstrap and signature checks remain enabled.

## Measured execution, 2026-11-13

ACT4 revision `56d40ab301dba23dd3104c17bd969afbaaea1931`, GCC 15.1
and Sail 0.15 built 610 ELFs. BOOM revision `0cb0b69`, preset `small`,
ran the instruction set before the privileged set. Core RTL is unchanged.

| Set | Built | Unique programs run | Latest C1 pass | Self-check/assert fail | RVFI error | Complete strict Spike match |
|---|---:|---:|---:|---:|---:|---:|
| Instructions | 378 | 378 | 376 | 2 | 0 | 0 |
| Privileged, M/S/U and Sv39 | 232 | 232 | 196 | 26 | 10 | 0 |

The first instruction run had 374 passes, two SC assertions and two false
REMW/REMUW monitor errors. A generic checker correction makes both word
remainder reruns pass. The table counts each ELF once. The privileged
table uses a fresh run after the canonical ECALL PC adapter correction.
An earlier privileged run had an input identity mismatch and is excluded.

Strict Spike checks ran on all 610 traces. All stop at unspecified reset
state differences in FCSR at the first mscratch write. There is
no complete strict match. No mask, synchronization or check waiver was
added. These are native execution counts, not architecture qualification.
The 38 remaining execution failures have retained findings. The reset
comparison limitation affects all 610 programs. See
[the failure groups and minimal programs](../../../../examples/boom/FINDINGS.md).

Remove `MUTABLE_MISA_B` when aggregate B is absent from the UDB profile.
Keep Zba/Zbb/Zbs selected. The generic suite loader permits explicitly
declared reference extensions without changing the trace ISA.

## Regeneration

From the workstation root, inspect selection with:

```sh
rvw regress plan --act4 rvw/configs/act4/boom/profile.json --json
```

Use a new build directory and two new run directories:

```sh
BUILD=rvw/out/act4-boom
rvw regress act4-build --profile rvw/configs/act4/boom/profile.json \
  --checkout "$ACT4_CHECKOUT" --out "$BUILD"
export ACT4_PROJECT_OUT="$BUILD"
scripts/with-lock.sh boom nice -n 10 rvw regress run --core boom \
  --suite act4-project --config small --filter '^rv64i/' --jobs 4 \
  --rvfi-trace --out "$INSTRUCTION_RUN"
scripts/with-lock.sh boom nice -n 10 rvw regress run --core boom \
  --suite act4-project --config small --filter '^priv/' --jobs 4 \
  --rvfi-trace --out "$PRIVILEGED_RUN"
rvw regress cosim "$INSTRUCTION_RUN" \
  --platform rvw/configs/act4/boom/platform.json
rvw regress cosim "$PRIVILEGED_RUN" \
  --platform rvw/configs/act4/boom/platform.json
```

Set `ACT4_PROJECT_OUT` to select another build directory. Set `SPINAL_BOOM`
to the private core checkout. Use the required core lock. The manifest
must verify the complete ELF set before suite filters apply.

`regress cosim` uses strict comparison. Raw build and run files stay local.
The frozen privileged run and two word reruns share RTL hash
`ca11548b40158b2e42030557d35ab512cce63f9406306aaea387875bc3bd6760`.
They use workstation base `eac5c2b` with this change's adapter repairs.
