# Virtual-memory requirement matrices

Use the existing `rvw regress mmu` commands. Select modes in a project-owned
copy of `matrix.json`. The example selects Sv39, Sv48, Sv57 and Sv32. Build
separate directories when the adapter uses different XLEN configurations.

```sh
rvw regress mmu build matrix.json --out out/vm-matrix --json
nice -n 10 rvw regress mmu reference out/vm-matrix --timeout 2 --json
```

Copy the suite from `regress.toml` into the project's regression config.
Set `configs` to the project's C1 adapter configurations. Run the suite through
`rvw regress run`. Use `rvw regress mmu check` and `report` for strict trace
checks and functional coverage. A Spike reference pass does not fill DUT bins.

The matrix covers R/W/X/U permissions, SUM, MXR, global leaf and non-leaf
mappings, MPRV, each superpage level, misaligned superpages, canonical addresses,
non-canonical faults, PMP-denied walks, Svade faults, Svadu updates, Bare mode,
mode changes, fence scopes and same-ASID root reuse. Sv32 has no non-canonical
address cases. Tests read satp back to reject an unsupported mode.

Programs check values or exact cause, tval and fault PC. Fetch tests enter real
S/U privilege. Data tests use MPRV. The physical layout is the existing MMU
layout. The largest table allocation is ten pages for a five-level root-reuse
case. Large virtual addresses do not allocate large physical memory regions.

## Limits

The matrix is bounded. It does not test every combination. A/D checks compare
final PTE contents. They do not establish atomicity or concurrent PTE safety.
The independent walk checker covers successful immutable mappings with preset
A/D bits. Missing observations remain inconclusive. Faulting walks, mutable
walk protocols, shared TLBs and cross-hart shootdowns need additional checks.
No RTL runs are part of the native Spike smoke test.

`extensions.json` is a separate opt-in Svnapot/Svpbmt campaign. It checks each
page in a 64 KiB NAPOT range, reserved NAPOT encodings, all PBMT encodings and
menvcfg.PBMTE controls. Build it in another empty directory. These results
cannot establish memory-type ordering or cache behavior. Independent bus
observations and a declared platform memory-type policy are still required.

`guest.json` contains six HLV.D cases. It checks nested VS/G translation,
VS page faults, G permission faults and mtval2. The G root uses Sv39x4
alignment and width. Separate G leaves map VS tables and payload. This is
not a complete hypervisor campaign. HFENCE scope effects, VMID reuse, nested
A/D, other x4 modes, VS fetch and independent nested walk checks remain open.

`shootdown.json` contains three two-hart mailbox tests. The remote hart primes
its translation. The local hart updates the PTE and publishes a request.
The remote hart fences before its acknowledgement. After completion, the
remote hart must read the new page value. Select a two-hart C1 configuration.
These tests use polling. They do not check interrupt delivery, OS scheduling,
shared-TLB internals or hardware translation-request completion signals.

`pointer.json` contains nine Smnpm cases across Sv39, Sv48 and Sv57. They
check disabled masking and PMLEN 7/16 with a tagged data pointer. They use
MPRV with effective S privilege and read menvcfg.PMM back before the access.
See the [pointer-masking specification](https://docs.riscv.org/reference/isa/priv/zpm.html).
Instruction-fetch, U-mode Ssnpm, M-mode Smmpm, debug and guest interactions
remain open. The installed Spike must support Smnpm for this campaign.
