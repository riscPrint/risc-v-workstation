# MMU suites contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Project-selected MMU matrices

`rvw.mmu/1` descriptions may contain `schema` and `matrix` instead of `schema`
and `scenarios`. `matrix` contains a nonempty unique `modes` list. Supported
modes are `sv32`, `sv39`, `sv48` and `sv57`. Expansion produces the same explicit
scenario records used by `rvw.mmu-build/1`. Scenarios may set `mode`; its default
is `sv39`. Levels range from zero to the selected mode's walk depth minus one.
Sv32 uses 32-bit PTEs, RV32 programs and nine ASID bits. Other modes use 64-bit
PTEs and sixteen ASID bits. Explicit non-canonical addresses require a
page-fault expectation. Existing schemas and default Sv39 behavior are retained.
Coverage groups are the scenario `bins`. Reference groups describe Spike only.
C1 coverage still requires the existing bound strict-check evidence.

Explicit MMU scenarios can select `napot` (RV64 boolean) and `napot_ppn`
(four low PPN bits, default 8). NAPOT cases use 16 equal level-zero PTEs.
`pbmt` selects a two-bit RV64 leaf encoding. `pbmte` selects menvcfg.PBMTE
(default true when pbmt is present). These scenarios check architectural
access or fault effects, not cacheability, ordering or device side effects.
`mode_switch` selects a translated/Bare/translated load check at the fixed
RAM payload. These options are opt-in and do not change old descriptions.

A scenario with `guest = true` selects an RV64 HLV.D test with Sv39 VS-stage
and Sv39x4 G-stage tables. `guest_flags` declares the G-stage payload leaf
permissions. `guest_fault` requires a load guest-page fault with checked
mtval2. `vmid` selects a 14-bit VMID. These cases require the H extension.
A scenario with `shootdown = true` selects a two-hart mailbox protocol for a
level-zero RV64 mapping. The Spike reference uses `-p2`. The C1 project must
select an adapter configuration with two harts. Request, acknowledgement and
completion use RAM mailboxes and explicit memory fences. No IPI is implied.
Neither option supports the independent immutable-walk checker yet.

## Guest pointer controls

`guest_pointer_matrix = {"modes": [...]}` selects VS/VU HLV/HSV masking and
HLVX exemption programs. Expanded scenarios have `guest_pointer` with
`pmlen` (0/7/16), `privilege` (S/U) and optional `context` (M/U).
The M-mode HLV/HSV accesses use
henvcfg.PMM for VS and senvcfg.PMM for VU. PMM readback is required. Tagged
HLVX addresses must fault regardless of PMM because HLVX is exempt from
masking. Disabled HLV/HSV masking must fault. Enabled masking must recover
correct data. Programs check exact cause, tval and PC on faults.
U-mode explicit HLV/HSV accesses use hstatus.HUPMM with HU enabled and VU
privilege. These scenarios use Ssnpm explicitly. Debug-state masking remains unsupported. Their independent nested-walk comparison remains
inconclusive because the nested reference does not model pointer transforms.

## Independent memory-type effects

A project `rvw.mmu-probes/1` declaration may also give `transactions` and
`ordering`. Each expected transaction has a unique `id`, physical `address`,
`access`, byte `width`, `memory_type`, and optional expected `data`. Ordering
is a list of before/after ID pairs. These are independent program/platform
expectations. Capture must not define the expected types or ordering edges.

The declared `bus_effect` probe records `id`, strictly increasing device-visible
`sequence`, physical `address`, `access`, `width`, `memory_type` and `data`
when needed. The checker detects wrong types, widths, data or addresses,
repeated/extra effects and violated declared ordering. Missing effects or
missing transaction plans remain inconclusive. The separate `memory_effects`
result does not earn a TLB/atomicity result. A memory-effect mismatch remains
a protocol mismatch. These checks require real independently observed device
effects. Request issue order alone is not device visibility. No global IO
ordering rule is assumed. The project must declare its supported policy.

## NAPOT range remapping

`napot_remap = true` selects a complete 64 KiB NAPOT range remap. It requires
RV64, a level-zero successful load, `napot = true`, `flags = "VRWAD"`, and
`fence` of all or va. The program primes all 16 pages, rewrites all 16 NAPOT
PTEs and checks every page's new data. An all fence invalidates globally. A va
campaign fences every 4 KiB page. It does not assume that one address-specific
fence invalidates an entire range cached as smaller entries. Missing DUT probe
observations remain inconclusive. This is an architectural remap check, not
proof of internal translation-cache granularity.

The per-level fault campaign now includes fetch as well as load and store.
Each mode checks invalid PTEs and PMP-denied PTE reads at every walk level.

## Nested C2 walk captures

C2 retirements may contain `mmu_nested_walks`. Each record gives `access_id`,
boolean `complete`, `vs_mode`, `vs_root`, `g_mode`, `g_root`, `va`, `access`
and `result`. Access is the permission operation; HLVX uses fetch permission.
The result has `status`, optional `pa` or fault `stage`/`htval`, `vs_walk` and
ordered `g_walks`. Each walk gives `status`, ordered PTE `reads` (level/address/
data/fault), and `pa` on success. G walks also give the translated `gpa` and
`access`. A G fault during a VS PTE read can leave `vs_walk` null.

`complete = true` declares capture of all VS/G table reads used by the modeled
translation. Cached or partial captures must set it false. They remain
inconclusive. The adapter must not reconstruct missing DUT reads from the
reference. `mmu report` compares complete records with the independent nested
walker. It uses table words from the hash-bound generated source and checks
G translation of every VS PTE read and the final payload. It supports fixed
preset-A/D mappings and fenced G-root reuse. Missing or unsupported references
remain inconclusive. C2 needs a passing end and complete C1 identity binding.
Incorrect complete records are mismatches. These checks do not fill
architectural bins. Functional groups can observe nested VS and G reads
separately, including partial capture observations.

## Random MMU programs and functional groups

`rvw.mmu/1` may contain `random` with selected `modes`, integer `seeds`, `pages`
and `accesses`. Pages are bounded to 1..64. Accesses are bounded to 1..128.
Each seed creates one program with multiple random mappings and load/store
accesses. PTEs select read/write, read-only, invalid or reserved level-zero
entries. Programs check each load, each exact trap cause/tval/PC and all final
physical data values. A/D bits are preset. Every access restores MPP before
MPRV so a prior trap cannot change the effective privilege. These are bounded
random programs, not exhaustive VM verification. The same ELF-dir C1 adapter
suites run them. `random_program` in expanded scenarios records seed and bounds.

MMU builds also write `functional-groups.json` for `rvw cov functional`.
Groups cross paging mode/access/result, levels/faults, PTE permissions,
translation protocols, harts, VS/G modes, pointer controls and IOMMU contexts,
stages and queues. C2 retirements may carry `mmu_protocol` and `iommu` lists
of captured dictionaries. Protocol records use `kind` and optional `hart`.
IOMMU records use `device`, `process`, `result`, `stage`, `access`, `queue`
and `operation` as applicable. Missing fields do not hit the affected group.
The coverage engine also consumes `mmu_walks`, hypervisor translations and
pointer CSR snapshots. C2/2 multi-hart traces keep separate dependency and
sequence histories for each hart and reset epoch. Coverage hits are capture
observations. They do not prove correctness or fill MMU architectural bins.
Missing captures remain holes. Hardware support and reachability are not
inferred from the declared domains.

## Decoded IOMMU scenarios

`rvw regress mmu iommu --generate --seed N --mode MODE` emits
`rvw.iommu-scenarios/1` data. `contexts` maps device IDs to decoded contexts.
A context can have `valid`, `first`, `second`, `processes` and `msi` fields.
First/second stages give `mode` (bare/sv39/sv48/sv57) and `root`. First stages
can set `privilege`. Process IDs map to first-stage contexts. Second stages use
x4 geometry. VS PTE reads also pass through second-stage translation.
`memory` gives physical PTE values. MSI `mask`/`pattern` selects page addresses;
`pages` maps selected page numbers to host page bases. These are decoded model
inputs, not raw architectural DDT/PDT/MSI structures.

`steps` contains `request`, `command`, `process_command`, `pte_write` and
`fault_pop` records. A request gives `device`, optional `process`, `address`,
`access` (load/store/fetch) and optional `size` (1/2/4/8). It must fit one page.
Decoded commands are `iotinval`, `iodir` and `iofence`, with optional device,
process and address scope. The model retains cached translations until an
invalidation. Queues have power-of-two `queue_size` with one slot reserved.
Full fault queues set `fault_overflow`. Faults have descriptive stage/cause
fields; these are not the architectural binary fault record encoding.

`rvw regress mmu iommu DESCRIPTION --observations FILE --result C1` compares
independent device-agent records. `rvw.iommu-observations/1` has `records`, C1
`identity` and `c1_sha256`. The C1 details must bind `iommu_description_sha256`.
All identity fields must match. Missing or unbound evidence stays inconclusive.
Mismatches remain mismatches. Reports use `rvw.iommu-check/1`. MCP exposes
`regress_mmu_iommu_generate` and `regress_mmu_iommu`. The Python device agent
calls a project-owned exchange callback with the same requests as the model.

The report records the pinned upstream reference-model revision. That pin is
source metadata. It does not mean that the C reference ran. Raw directory and
register conformance, ATS, PRI, atomic A/D, MSI wire formats and DUT transport
integration remain unsupported by this decoded model.

## Hypervisor MMU matrices

`rvw.mmu/1` may contain `guest_matrix = {"modes": [...]}` instead of scenarios.
Supported modes are sv39, sv48 and sv57. The generator crosses the selected
VS and x4 G geometries. Guest scenarios may give `guest_mode`, `guest_op`
(hlv.d, hlvx.wu, hsv.d, vs-satp, vs-sfence, vs-sret), `guest_trap` (m or hs),
and boolean `guest_switch`. VS controls require `expect = "virtual-instruction"`.
`ad_mode` and `ad_expect` select VS-stage A/D behavior and check the full PTE.
G roots have 16 KiB alignment and widened top-level indices. hgatp and vsatp
readback must preserve the selected modes. G faults check mtval2 or htval and
mtinst or htinst. Trap-instruction values may be zero or the specified
transformed instruction. `guest_switch` uses two G roots with different payloads
under the same VMID. It fences each switch, including reuse. It requires a
successful M-mode HLV.D test. Independent `mmu_nested.translate` checks G walks
for every VS PTE read as well as for the final payload. Its Python results do
not imply DUT capture or nested-walk comparison. Hardware A/D and extension
PTE walk models remain outside its scope.

## Translation protocol probes

`rvw regress mmu report --protocol-config FILE` reads `rvw.mmu-probes/1`.
The project declares `harts`, a `probes` object that maps event kinds to probe
paths, and optional `pbmt_types` mapping PBMT numbers as strings to memory-type
names. The example paths and memory-type names require project replacement.
Events remain in the identity-bound `rvw.mmu-observations/1` sidecar.
Each has an ordered `cycle` and `kind`. Translation events give `hart`.

`pte_write` gives physical `address` and `data`. `ad_atomic` gives `address`,
`old`, `new` and `set_bits` (64 or 192). The old value must equal the current
observed PTE. The new value must preserve all bits except the set A/D bits.
`tlb_fill` gives `entry`, aligned `va`/`pa` bases, power-of-two byte `size`,
`asid`, optional `global`, `pte_address` and `pte`. A fill must use the current
observed PTE. `tlb_hit` gives `entry`, `va`, `pa` and `asid`. It must match a
retained entry. `tlb_invalidate` is a completion with `va` and `asid`, each
nullable for all addresses or all ASIDs. An address invalidates the containing
range. ASID-specific invalidations preserve global entries.

`shootdown_request` gives unique `request`, target hart list `targets`, and
optional `va`/`asid` scope. `shootdown_ack` gives `request` and `hart`.
It requires a prior matching local invalidation completion. A
`shootdown_complete` requires every target acknowledgement. `memory_type`
gives `pbmt` and `memory_type`; it requires the explicit project policy.
Missing initial PTEs, unfinished requests and absent probes are inconclusive.
Protocol results remain separate from architectural coverage. This checker
does not infer missing events, bus ordering or cache coherence.

MMU `atomic_ad = true` selects a two-hart RV64 store with hardware A/D and a
software AMO update to RSW. The final full PTE must contain both updates.
It does not establish that DUT updates overlap. A `shootdown` scenario can
provide `ipi` with project-owned `msip` base and per-hart `stride`. It delivers
an actual M software interrupt before local SFENCE and acknowledgement.

## Ordered MMU walk observations

C2 retirements may contain `mmu_walks`, a list of completed walk records.
Each record has `kind = "mmu_walk"`, sequential integer `access_id`, `mode`
(Sv32/39/48/57 in lower case), `access` (load/store/fetch), `va`, `root`,
`status` (success/page-fault/access-fault), and ordered `reads`. Successful
records also give `pa`. Addresses and PTE data use integers or integer strings.
Each read gives integer `level`, physical `address`, boolean `fault`, and
`data` when the read succeeds. PMP-denied reads have `fault = true`.
The adapter captures these from project-declared probes. It must not synthesize
walk records from retirement results. `access_id` follows the scenario's tested
accesses, excluding harness accesses. A project must capture all tested walks
for a complete comparison. A TLB hit that has no walk leaves this comparison
inconclusive. No TLB hit coverage is implied.

`rvw regress mmu report` checks bounded data scenarios against an independent
Python walker. Reference PTE snapshots come from the scenario generator, never
from DUT returned PTE data. Fenced leaf remaps use separate memory snapshots.
The checker compares every level, PTE address, PTE value and final result.
C2 must have a passing end and its core/config/ELF/RTL/source/seed identity must
match C1. Missing records remain inconclusive. Incorrect or extra records are
mismatches. These results do not fill architectural bins. Hardware A/D writes,
extension PTEs, root switches and unfenced alternatives are unsupported here.

MMU scenarios may set `pte_fault_level` or `walk_deny_level`. The named level
must exist in the selected page table. The first option invalidates its PTE.
The second denies PMP reads of only that table page. Programs check the exact
page/access fault, tval and PC. These fields require the matching fault
expectation and exclude remapping and blanket walk denial.
