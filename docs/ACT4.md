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

The platform supplies ISA and privilege selection. UDB parameters describe
settings that an ISA string cannot express. The linker and macros supply
the RAM, reset, signature and halt conventions. Review all inputs against
the adapter. Generic code has no core names, signal names or test lists.

Set `test_extensions` to select declared instruction groups. Alternatively,
set `all_applicable: true` to let pinned ACT4 metadata select all applicable
groups, including privileged directories by default. Do not set both.
State absent devices and model-only devices in `limits`.

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
| VexiiRiscv RV32IMA M/S/U, standard boot | 270 | 270 | 0 | 270 | 0 | 270 |
| Bundled BOOM profile | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN | NOT RUN |

The instruction profiles use a reduced CSR boot. They retain every selected
test body and signature check. They do not establish standard Sm
compatibility. Each profile has I: 39, M: 8, Zmmul: 4, Zicsr: 6 and
Zifencei: 1. Only VexRiscv's six Zicsr cases fail. They retain MEPC alignment
bits. Writes of 1, 2 and 3 reproduce the finding. The same controls pass
on VexiiRiscv. The original standard bootstrap failed all 58 cases on both
cores. Those failures remain in each profile's observation file.

The supervisor profile keeps the standard boot. It builds 201 tests from
privileged directories and 69 instruction tests. All 270 first traps occur
on the mhpmevent3 write before the test body. None reaches
`rvtest_code_begin` or retires an instruction in its symbol-delimited body.
One strict Spike comparison per group, 37 comparisons, confirms that first
difference. These comparisons do not qualify the complete traces.

The bootstrap gap is a core compatibility finding under the selected
scaffold. The exact core and firmware CSR contract remains open. It is not
a proved hardware defect. No failure is waived. The supervisor profile has
no program-controlled IRQ devices. Model-only Sail devices do not establish
DUT interrupt-device support.

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
- [BOOM configuration only](../rvw/configs/act4/boom/README.md).

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

The BOOM profile has configuration and unit tests only. Its ACT4 compilation,
elaboration, simulation and reference comparison were NOT RUN. Historical
BOOM results do not qualify it. No full Python suite or GitHub CI run is
claimed for this work. riscv-dv and TestRIG are separate integrations.
