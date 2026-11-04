# Open workloads

`rvw workloads` builds pinned application kernels and checks their outputs with
Spike or QEMU. It does not run a core or issue a gate verdict. See
[the comparison](../../../../docs/WORKLOADS.md) for selection and sampling limits.

## Default set

The default is six Embench-IoT 1.0 kernels: crc32, matmult-int, slre,
nettle-aes, minver and nbody. The source commit, full compiler version line,
flags, input policy and checker policy are in [default.json](assets/default.json).
This is a smoke set. It is not a compliant Embench score or a SPEC substitute.
Sources are not vendored. Preserve upstream notices when distributing binaries.

```sh
git clone https://github.com/embench/embench-iot.git /path/to/embench
rvw workloads list --json
nice -n 10 rvw workloads build --source /path/to/embench --out /path/to/build
nice -n 10 rvw workloads verify --build /path/to/build/build.json \
  --out /path/to/reference --oracle spike --timeout 120
```

Use `--bench crc32,nbody` to select kernels. Each output directory must be new.
Git archive captures the pinned commit. Working-tree changes have no effect.
The build records source and runtime hashes, compiler path/version/hash,
commands, ELF hashes and sizes. Verification checks the source and ELF hashes,
then requires reference exit 0 and the exact expected stdout hash.
The bare-metal wrapper calls the upstream checker and requires exactly 1.
It sends failure to HTIF for 0 or -1. Stdout must be empty.
FP uses the upstream tolerances. Fast math and FP contraction are disabled.
Startup clears BSS, sets the stack and global pointer, and enables FP.
It supports one active hart. It uses an HTIF exit, not Linux syscalls.

## Local Linux or licensed SPEC hook

Pass `--manifest /path/to/local.json` to `list` or `build`. The same `verify`
command accepts the resulting build report. Linux mode requires a static
RV64 Linux executable and `--oracle qemu-riscv64` (or qemu-riscv64-static).
This user-mode engine is not available in the native macOS QEMU package.
Use a native Linux host. Dynamic sysroots are not supported by this first flow.

The JSON manifest has schema `rvw.workloads/1`, a nonempty `compiler_version`
(full first `CC --version` line), and a nonempty `workloads` list.
Pin sources with a full Git `revision`, or a `source_sha256` tree hash.
Use `rvw.workloads.core.tree_hash(Path(...))` on an extracted source tree.
This hash includes relative file names, contents, execute bits and internal
symlink targets. External and broken symlinks are errors.
Each workload has:

| Field | Meaning |
|---|---|
| `id` | Unique lowercase name; letters, digits, underscore and hyphen |
| `mode` | `bare` for Spike or `linux` for QEMU user mode |
| `build` | Nonempty argv array; no shell evaluation |
| `args` | Run argv array; paths are relative to the captured source tree |
| `stdout_sha256` | Exact expected stdout SHA-256; reference exit must be 0 |

Build arguments support `{cc}`, `{source}`, `{out}` and `{assets}`.
Write the executable to `{out}/workload.elf`. Keep generated files under
`{out}`. Source files must stay unchanged. Use a checked-in build script for
multi-step builds. Pin the script, input data and checker in the source tree.
Run inputs get a separate copy for each workload. Generated databases and
other run outputs cannot change the captured input tree.

For SPEC CPU2017, keep all licensed sources, inputs, result files and manifests
outside this repository. Supply a local wrapper and pin its complete source
and input tree. The wrapper builds the selected benchmark for RV64GC Linux.
Run the application through a guest driver that invokes the official output
validator. Make the driver return nonzero on any invalid or absent output.
Have it print a fixed validation line. Pin that line's hash in the manifest.
Do not hash timing text or use a successful compiler exit as a result check.
No SPEC files are downloaded or distributed. No SPEC scores are calculated.
The hook is the same manifest flow; it does not implement or qualify `runcpu`.

## Decisions and limits

- Keep the runner generic. No core signals or presets are embedded.
- No implicit downloads, compiler substitution or cache reuse occur.
- A failed command leaves an incomplete directory without build.json.
  Use a new output path for the next attempt.
- The default compiler is RV64 GCC 15.1.0 with the exact build line in the pin.
  A different build needs a separate explicit manifest. The report hashes its
  executable. Keep the complete toolchain distribution with the experiment.
  GCC's assembler, linker, newlib and sysroot are not independently captured.
- A local build script's host dependencies are the caller's responsibility.
  The manifest hook is not a complete C8 build capture or sandbox.
- Only stdout and exit status are checked automatically. Use a guest checker
  for file outputs. A driver that prints success without checking is invalid.
- The Linux and SPEC hooks have unit tests. Native Linux application builds,
  SPEC runs, RTL runs and sampling restore are not qualified by those tests.
- MCP bindings and automatic sampling are not implemented.

Use `verify --trace` with Spike to retain its instruction log in each stderr
file and add dynamic opcode categories to verify.json. Counts include startup,
checker and compressed instructions. FP memory instructions occur in both the
FP and load/store categories. Conditional branch transitions give taken counts,
not predictor misses. The profile leaves cache and predictor miss fields null.
Instruction logs can use much more disk space than the ELFs.
