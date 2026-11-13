# ACT4 suites

ACT4 builds self-checking RISC-V architectural tests. The workstation uses
ACT4's Sail signatures, the generic C1 run adapter and strict Spike
comparison. A passing test does not establish architectural certification.

## Project description

Keep the profile beside the core project. Use `rvw.act4/1` JSON with these
project inputs:

- A pinned ACT4 revision and platform JSON path.
- The ISA string, XLEN, privilege modes, RAM map and reset address.
- UDB extension versions and core-specific WARL and device parameters.
- A Sail configuration, linker script and `rvmodel_macros.h`.
- `tohost-1-3`: 1 means pass and 3 means fail.

The UDB architecture name includes a hash of the declared extensions and
parameters. The test configuration name remains `rvw-act4`. This prevents
UDB's shared named cache from supplying another architecture's generated
headers. A stale RV64/F header was observed during the RV32IMC Ibex build.

The platform supplies ISA and privilege selection. UDB parameters describe
settings that an ISA string cannot express. The linker and macros supply
the RAM, reset, signature and halt conventions. Review all inputs against
the adapter. Generic code has no core names, signal names or test lists.

Set `test_extensions` to select declared instruction groups. Alternatively,
set `all_applicable: true` to let pinned ACT4 metadata select all applicable
groups, including privileged directories by default. Do not set both.
State absent devices and model-only devices in `limits`.

An optional `csr_model` binds a project `rvw.csr-selection/1` file to the
profile. The model must have the same XLEN. Its `binding.platform` must
equal the profile platform path. The plan uses the shared CSR catalog to
report explicit absences under simple extension requirements. It leaves
omitted CSRs and complex predicates unknown. `missing-required` is a
compatibility finding. It does not remove bootstrap accesses or skip tests.
The build manifest hashes the CSR model.

## Build, select, run and compare

Install the pinned ACT4 prerequisites, RISC-V GCC and Sail. The measured
builds below use GCC 15.1.0 and Sail 0.15. Put them on PATH. Keep the ACT4
checkout outside the project. Use a new build output directory.

From the core project:

```sh
rvw regress plan --act4 rvw/act4/profile.json --json
rvw regress act4-build --profile rvw/act4/profile.json \
  --checkout "$ACT4_CHECKOUT" --out rvw/out/act4
rvw regress list --suite act4 --json
rvw regress run --suite act4 --rvfi-trace --out /tmp/act4-run
rvw regress cosim /tmp/act4-run --platform rvw/platform.json
```

Declare the ELF suite in `rvw.toml`:

```toml
[suites.act4]
dir = "rvw/out/act4/work/rvw-act4/elfs"
act4_manifest = "rvw/out/act4/manifest.json"
glob = "**/*.elf"
strip_suffix = ".elf"
```

Add the project's adapter configuration and run limits. The build runs
Sail to obtain expected signatures, then compiles them into each final
self-checking ELF. C1 observes tohost completion. Signature failure remains
failure. The manifest binds the whole ELF set and hashes before filters
apply. It records build inputs, tool hashes, signature hashes and selection.
A successful build is not a DUT pass.

`rvw regress cosim` compares passing C1 results. It retains failed C1
results as failures. To inspect a failed trace's first reference difference,
run `rvw cosim check --strict --elf ELF --trace TRACE --platform PLATFORM
--core CORE --json`. A mismatching prefix is not a complete trace match.
Review the applied policy. The measured passing ACT4 results below use
zero synchronization and zero output masks.

On macOS, UDB can download a Linux Z3 library. Use a private XDG cache with
`udb/z3/<version>/arm64/libz3.so` linked to the installed `libz3.dylib`.
Keep UV_CACHE_DIR and MISE_CACHE_DIR at their normal locations. Do not
change a shared cache.

## Native results on 2026-11-13

ACT4 revision: `56d40ab301dba23dd3104c17bd969afbaaea1931`.
VexRiscv revision: `baf7dc82f855eddaf5b0a20a6802c526f127e38a`.
VexiiRiscv revision: `9f70315deb3390b283995c5b8f1bd38215ecf52b`.
These are native RTL simulations. Core sources were not changed.

| Profile | Built | Run | C1 pass | C1 fail | Complete strict Spike match | Finding cases |
|---|---:|---:|---:|---:|---:|---:|
| VexRiscv RV32IM instruction profile | 58 | 58 | 52 | 6 | 52 | 6 |
| VexiiRiscv RV32IM instruction profile | 58 | 58 | 58 | 0 | 58 | 0 |
| VexiiRiscv RV64IMA machine instruction profile | 98 | 98 | 98 | 0 | 98 | 0 |
| VexiiRiscv RV64IMA M/S/U, Sv39 | 302 | 302 | 0 | 302 | 0 | 302 |
| VexiiRiscv RV32IMA M/S/U, standard boot | 270 | 270 | 0 | 270 | 0 | 270 |
| NaxRiscv RV32IMA instruction profile | 69 | 69 | 69 | 0 | 69 | 0 |
| NaxRiscv `rv64ima` instruction profile | 98 | 98 | 98 | 0 | 98 | 0 |
| NaxRiscv `rv64imasu` instruction profile, M boot | 98 | 98 | 98 | 0 | 98 | 0 |
| PicoRV32 RV32IM mapped Verilog profile | 51 | 51 | 50 | 1 | 50 | 1 |
| Bundled BOOM small instructions | 378 | 378 | 376 | 2 | 0 | 2 |
| Bundled BOOM small privileged | 232 | 232 | 196 | 36 | 0 | 36 |

The two Vex instruction profiles use a reduced CSR boot. They retain every
selected test body and signature check. They do not establish standard Sm
compatibility. Each has I: 39, M: 8, Zmmul: 4, Zicsr: 6 and Zifencei: 1.
Only VexRiscv's six Zicsr cases fail in these two profiles. They retain MEPC alignment
bits. Writes of 1, 2 and 3 reproduce the finding. The same controls pass
on VexiiRiscv. [The six MEPC decisions](../examples/vexriscv/rvw/act4/MEPC_DECISIONS.md)
retain them as core readback differences. The independent MPP and interrupt
mtval findings do not permit these MEPC values. The original standard
bootstrap failed all 58 cases on both cores. Those failures remain in each profile's observation file.

The supervisor profile keeps the standard boot. It builds 201 tests from
privileged directories and 69 instruction tests. All 270 first traps occur
on the mhpmevent3 write before the test body. None reaches
`rvtest_code_begin` or retires an instruction in its symbol-delimited body.
The fresh stable-checkout rerun has 270 C1 failures and 270 strict Spike
first differences at that instruction. No complete match is earned. The
earlier 37 representative comparisons remain historical evidence.

The shared catalog defines mhpmevent3 under Sm. The selected profile omits
the upstream counter plugin that supplies zero-valued event selectors.
The project-bound CSR model records this explicit absence. This is one
declared-profile CSR compatibility finding affecting 270 cases. It is not
270 independent core defects. No bootstrap access or failure is waived.
The supervisor profile has no program-controlled IRQ devices. Model-only Sail devices do not establish
DUT interrupt-device support.

NaxRiscv uses a machine-mode signature profile on the unchanged MSU RTL
target. Its 69 tests include nine Zaamo and two Zalrsc cases. All 69 pass
and have complete strict Spike matches. Standard Sm and supervisor ACT4
on NaxRiscv remain NOT RUN. PicoRV32 uses a CSR-free bootstrap on the
`rvw init --hdl sv` mapped adapter. Of 51 tests, 50 pass and match strictly.
`I-fence-00` remains failed: FENCE with rd=x1 changes destination state.
The shared PicoRV32 cosim platform declares its raw `full_word` load view.
This is checked transport normalization, with zero output masks and zero
synchronization. No core source was changed.

The same supervisor profile passes all 49 riscv-tests with complete strict
Spike matches. VexiiRiscv's machine profile also has 49 strict riscv-tests
matches. VexRiscv's 49 riscv-tests pass C1, but the stock reset stub has an
initial CSR snapshot difference under the stricter policy used here.
Those traces are not counted as qualified strict matches.

See the project records for exact per-extension counts, ELF hashes,
first differences, build inputs and minimal reproductions:

- [VexRiscv instruction profile](../examples/vexriscv/rvw/act4/README.md).
- [VexiiRiscv instruction profile](../examples/vexiiriscv/rvw/act4/README.md).
- [VexiiRiscv supervisor profile](../examples/vexiiriscv/rvw/act4-supervisor/README.md).
- [NaxRiscv instruction profile](../examples/naxriscv/rvw/act4/README.md).
- [PicoRV32 mapped Verilog profile](../examples/picorv32/rvw/act4/README.md).
- [BOOM native execution and findings](../rvw/configs/act4/boom/README.md).

## Functional coverage and holes

The saved reports use the real `rvw cov functional` command. Each observed
merge includes all ACT4 traces and 49 riscv-tests traces. Failed prefixes
remain visible. Each qualified report requires C1 pass and a complete
strict Spike match. Different ISA contexts remain separate.

| Profile | Observed traces | Qualified traces | Observed default-domain holes |
|---|---:|---:|---:|
| VexRiscv machine | 107 | 52 | 42 |
| VexiiRiscv machine | 107 | 107 | 42 |
| VexiiRiscv supervisor | 319 | 49 | 34 |
| VexiiRiscv supervisor, with generated random/PMP suites | 717 | 447 | 24 |

The final supervisor merge adds four generated random privilege programs
and 394 generated PMP programs. All 398 were rerun and have C1 passes
and complete strict Spike matches. The new [coverage review](../examples/vexiiriscv/rvw/act4-functional/review/README.md)
uses pinned opcode bins. Qualified instruction holes remain in A and
Zicsr. ECALL/EBREAK holes in the nontrapping instruction domain must be
read with the trap groups. Other generated IRQ/MMU corpora are not merged.
The older 319/49 row remains historical.

Coverage includes boot and signature checks. It does not isolate ACT4 test
bodies. The failed supervisor prefixes do not qualify privileged behavior.
Default domains are a plan, not an ISA support or reachability claim.
Groups without fixed bins have no completeness percentage. No unknown
encodings were recorded in these corpora.

The reports retain raw C2 hashes and exact corpus membership. Paths are
rebased for publication. The merge checks unique hashes, summed instruction
records and every bin count. Full hole lists for observed and qualified
streams are in the [VexRiscv reports](../examples/vexriscv/rvw/act4-functional/README.md)
and [VexiiRiscv reports](../examples/vexiiriscv/rvw/act4-functional/README.md).

## Limits

The BOOM profile built and ran 610 programs. Its 38 execution failures
include 10 RVFI monitor errors. All strict Spike comparisons stop at
unspecified reset FCSR state. No complete strict match is earned.
See the [BOOM profile](../rvw/configs/act4/boom/README.md) and its findings. No full Python suite or GitHub CI run is
claimed for this work. riscv-dv and TestRIG are separate integrations.

The [RV64 machine record](../examples/vexiiriscv/rvw/act4-64m/README.md)
retains all 98 strict matches and extension counts. It uses reduced CSR boot.
The [RV64 supervisor profile](../examples/vexiiriscv/rvw/act4-64su/README.md)
keeps standard boot and the explicit missing `mhpmevent3` finding. All 302 cases fail at the standard boot write to `mhpmevent3`, before their
test bodies. No complete strict match is claimed. This is one compatibility
finding across 302 cases. Its PMP granularity is 16 bytes and NA4 is absent.


## NaxRiscv RV64 instruction profile

The [RV64 profile](../examples/naxriscv/rvw/act4-rv64/README.md) uses a
machine-mode Sail signature model for both target configs. It retains all
98 selected test bodies and signature checks. Both targets have 98 C1
passes and 98 complete strict Spike matches, with zero synchronization
and no output masks. Standard Sm, S/U ACT4 and Sv39 ACT4 remain NOT RUN.
The generated supervisor suites are separate results.


## Extra VexiiRiscv FP profiles

| Config | ACT4 groups | Built | C1 pass | Strict Spike match |
|---|---|---:|---:|---:|
| RV32IMAFC | F 80, Zca 26, Zcf 4 | 110 | 110 | 110 |
| RV64IMAFDC | F 84, D 116, Zca 32, Zcd 4 | 236 | 236 | 236 |

These machine-mode profiles use core `9b63f47fe559dbba7874af9196746412fa1294c1`
and ACT4 `56d40ab301dba23dd3104c17bd969afbaaea1931`. They use the reduced
CSR bootstrap and complete C2/2 FP/CSR captures. There is no synchronization
or mask. The [FP README](../examples/vexiiriscv/rvw/fpu/README.md) gives the
commands and limits. A separate flags-only FS test finds a core defect on
both widths. The ACT4 passes do not close that defect or establish certification.
