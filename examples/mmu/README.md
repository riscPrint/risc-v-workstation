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
The raw-request walk checker covers successful immutable mappings with preset
A/D bits. The C2 checker below also supports faulting walks and fenced leaf
changes. Missing observations remain inconclusive. Hardware A/D updates,
shared TLBs and cross-hart shootdowns need additional checks.
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
A/D, other x4 modes and nested checks are covered by the later matrix and
capture checker. Full VS fetch and HFENCE scope campaigns remain open.

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
The later campaigns add tagged fetch, Ssnpm, Smmpm and guest data masking.
Debug-state masking remains open. The installed Spike must support Smnpm for this campaign.

`fault-walks.json` adds 84 short cases. Each mode tests an invalid PTE and a
PMP-denied table read at every level, for loads, stores and fetches. Build these with
`rvw regress mmu build` and use the same C1 suite pattern. Select the scenarios
for the project's XLEN before building. `mmu report` also accepts ordered C2
`mmu_walks` records. Its independent checker supports faulting walks and fenced
leaf changes with preset A/D bits. The older raw-request checker retains its
successful immutable scope. No DUT walk result is claimed from Spike alone.

`protocol.json` has three two-hart A/D versus RSW cases and three IPI shootdown
cases. The interrupt map is project data and must match the adapter. Spike
uses its standard MSIP map. The final full PTE must preserve both updates.
Reference interleaving does not prove physical overlap. `probes.json` shows
the optional project probe and PBMT policy declaration for `mmu report
--protocol-config`. Replace all probe paths with the project's capture points.
No type policy means no PBMT transaction verdict. Missing protocol evidence
remains inconclusive. Ordering and shared-TLB hardware validation remain open.

`hypervisor-matrix.json` selects 102 programs with VS Sv39/48/57 and G x4
geometries, HLV/HLVX/HSV, VS/G faults, VS A/D, virtual-instruction traps,
HS fault CSRs and same-VMID root reuse. The root-reuse cases allocate a second
payload 2 MiB away. This is a bounded reference campaign. Independent nested
DUT captures, full HFENCE scopes and guest fetch matrices remain open.

`pointer-privileges.json` adds 54 cases for Ssnpm, Smmpm, explicit Sspm/Supm
controllers and tagged fetch faults. Select only the project's extensions.
Sspm/Supm describe execution-environment capabilities. They need explicit
controller choices in this backend. The guest-pointer campaign adds VS/VU
hypervisor data masking. Debug interactions remain open.

`random.json` creates eight deterministic programs with eight mappings and 32
random accesses each. Select modes and seeds in the project. Bounds are 64
pages and 128 accesses. Programs check each result and the final data state.
All MMU builds also write `functional-groups.json` for `rvw cov functional`.
C2/2 multi-hart coverage keeps separate histories per hart and epoch. Groups
need actual walk, protocol, pointer, hypervisor or IOMMU capture fields. Missing
fields produce holes. Coverage observations do not establish correctness.

`napot-range.json` has six full-range remap programs. Each primes all 16 pages
of a 64 KiB NAPOT mapping, changes all PTEs and checks all new values after a
global fence or 16 per-page fences. It makes no internal cache-granularity
claim. The per-level fault matrix now includes instruction-fetch cases.

`guest-pointer.json` contains 81 Ssnpm cases. It checks VS/VU HLV and HSV
masking through henvcfg/senvcfg and confirms that HLVX remains unmasked.
U-mode HUPMM controls are also checked. Debug-state masking remains open. The independent
nested walker does not yet model pointer transforms and stays inconclusive.

## RTL results

On 2026-11-13 the VexiiRiscv supervisor profiles ran the satp-mode subsets.
Strict Spike comparison with `rvw regress cosim`:

| Profile | Description | Generated (mode) | Applicable | C1 pass | Spike match | Finding |
|---|---|---|---|---|---|---|
| `rv64imasu` Sv39 | `matrix.json` | 589 (147) | 145 | 143 | 143 | 2 |
| `rv64imasu` Sv39 | `fault-walks.json` | 84 (18) | 18 | 9 | 9 | 9 |
| `rv64imasu` Sv39 | `random.json` | 8 (2) | 2 | 2 | 2 | 0 |
| `rv32imasu` Sv32 | `matrix.json` | 589 (142) | 140 | 138 | 138 | 2 |
| `rv32imasu` Sv32 | `fault-walks.json` | 84 (12) | 12 | 6 | 6 | 6 |
| `rv32imasu` Sv32 | `random.json` | 8 (2) | 2 | 2 | 2 | 0 |

Hardware A/D scenarios are not applicable. All findings are one core defect:
the page walker reads PTEs that PMP denies. The C2 `mmu_walks` check matched
92 Sv39 and 89 Sv32 matrix scenarios and 10 fault-walk scenarios against the
independent walker. See the
[VexiiRiscv README](../vexiiriscv/README.md#generated-suites-on-rtl-2026-11-13)
for the commands, the exclusions and the inconclusive cases. Sv48, Sv57, H,
pointer masking, NAPOT, PBMT and shootdown suites have no RTL target yet.

The matrix subsets are now counted separately in the
[detailed family table](../vexiiriscv/README.md#detailed-family-results-2026-11-13).
Per profile, both applicable Svade programs and all ten TLB/ASID/fence programs
pass RTL and match Spike. The remaining translation programs have the two
PMP-denied-walk findings. Their [triage](../vexiiriscv/findings/ptw-pmp/README.md)
confirms a core defect with a directed program and a short wave window.
