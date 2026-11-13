# ACT4 instruction profile

This profile runs I, M, Zmmul, Zicsr and Zifencei tests through C1. It uses a
reduced CSR boot to reach the instruction test bodies. It does not establish
standard Sm compatibility. The standard-boot failures remain open core
findings in `observations.json`. No test body or signature check is removed.

The linker emits real instructions at reset to clear mscratch and mtvec.
Both the DUT and the reference execute them. Comparison uses strict mode.
No CSR output mask or synchronization is allowed.

## Build and run

Install the pinned ACT4 prerequisites, Sail 0.15 and RISC-V GCC. Put their
executables on PATH. Keep ACT4 outside this project at revision
`56d40ab301dba23dd3104c17bd969afbaaea1931`.

From the core project, run:

```sh
rvw regress plan --act4 rvw/act4/profile.json --json
rvw regress act4-build --profile rvw/act4/profile.json \
  --checkout "$ACT4_CHECKOUT" --out rvw/out/act4
rvw regress run --suite act4 --rvfi-trace --out /tmp/act4-run
rvw regress cosim /tmp/act4-run --platform rvw/platform.json
```

Use a new build output directory. The suite checks the manifest and all ELF
hashes before discovery. On macOS, the UDB cache can contain a Linux Z3
library. Use a private XDG cache with `udb/z3/<version>/arm64/libz3.so`
linked to the installed `libz3.dylib`. Keep UV_CACHE_DIR and MISE_CACHE_DIR
at their normal locations. This workaround changes no shared cache.

ACT4 needs CLINT and simple_interrupt_generator in the Sail signature
model. These model-only regions are outside DUT RAM. They do not establish
DUT device support. The DUT profile has no program-controlled IRQ devices.

## Native observations

On 2026-11-13, all 58 selected ELFs built and ran. C1 reported 52 pass and
6 fail. 52 passing cases have complete strict Spike matches with zero
masks and zero synchronizations. The detailed rows and hashes are in
`observations.json`. The standard boot failed all 58 cases before the test
bodies. Those failures are retained separately. The six Zicsr failures retain MEPC alignment bits. The standard boot also traps on mstatush (0x310).

These are native RTL simulation results. They are not hardware results,
certification, or a passing Sm test suite. The original riscv-tests reset
stub is separate from this ACT4 reset veneer.

## Reproductions

`missing-boot-csr.S` reproduces the startup trap. Set CSR_ADDR to 0x310 on
the first profile or 0x323 on the second profile. `mepc-low-bit.S` writes 1
to MEPC. VexRiscv reports fail; VexiiRiscv reports pass. `mepc-alignment.S`
accepts MEPC_VALUE to reproduce either low alignment bit.

```sh
riscv64-unknown-elf-gcc -march=rv32i_zicsr -mabi=ilp32 -nostdlib \
  -T rvw/act4/link.ld -DMEPC_VALUE=2 rvw/act4/mepc-alignment.S \
  -o /tmp/mepc.elf
rvw/run.sh run --elf /tmp/mepc.elf --out /tmp/mepc-run \
  --config rv32im --seed 1 --mem-latency 0 --rvfi-trace
rvw cosim check --core vexriscv --platform rvw/platform.json \
  --elf /tmp/mepc.elf --trace /tmp/mepc-run/rvfi.jsonl --strict --json
```

UDB 0.1.17 `csr/mepc.yaml` requires bits 1:0 to read zero for this
uncompressed ISA. The VexRiscv source pin maps MEPC as an unrestricted
read/write register in `CsrPlugin.scala`. Core sources remain unchanged.

See [the six MEPC decisions](MEPC_DECISIONS.md) for minimal programs,
strict Spike first differences and comparison with the formal ISA and
interrupt findings. All six remain core readback differences.

Historical `observations.json`: {"date":"2026-11-13","evidence":"native instruction-only ACT4 with reduced CSR boot; not Sm compatibility or certification","build_inputs":{"entries":4},"tools":{"entries":2},"reference_policy":"strict; no synchronization or masks","counts":{"entries":5},"tests":{"records":58},"baseline":{"entries":2},"minimal_reproduction_counts":{"fail":2},"minimal_reproductions":{"records":4},"workstation_dirty":true,"core_dirty":true,"core_fingerprint":"ed26b3bf284aaf5157f3b9c2807e8471887ea7b4ff048e9cfbe3013cf3136191","tools_key":"fb39d5a7314b62e7c95cf7da0943d8169f24f7c9e0f18d002abbc1cf6a2f139d"}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw regress run --suite act4 --rvfi-trace --out RUN_ROOT`. Use the pinned inputs and options from [PR #1100](https://github.com/riscPrint/risc-v-workstation/pull/1100).
