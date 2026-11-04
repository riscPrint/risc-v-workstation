# Open workloads for RV64GC

Use the six pinned Embench kernels as the default **smoke set**. Add a Linux
application tier before using the set for architecture ranking. Keep licensed
SPEC CPU2017 optional. No open suite here establishes SPEC representativeness.
The runner and exact pins are in [workloads](../rvw/src/rvw/workloads/README.md).
Measured build and reference results belong in issue #282 and its pull request.

## Candidate comparison

Sizes below describe proposed input scales, not measured resident memory.
Behaviour columns are source-based expectations, not cache or predictor results.
Unless a row names the default kernels, local RV64 build status is **not verified**.
Portable C/C++ is a porting route, not evidence of a successful RISC-V build.

| Candidate and licence source | Integer / FP behaviour | Branch / memory behaviour | Size and input sets | RV64 build route and status |
|---|---|---|---|---|
| [CoreMark-PRO](https://github.com/eembc/coremark-pro), [custom acceptable-use agreement](https://github.com/eembc/coremark-pro/blob/main/LICENSE.md) | Mixed integer and FP; nine workloads | Algorithms, loops and larger data sets | Upstream reference data; configurable contexts | Needs a platform port; not verified. Exclude from the unrestricted default because result publication has licence conditions. |
| [Embench-IoT](https://github.com/embench/embench-iot), GPL-3.0-or-later support code; inspect per-file notices | Crypto, text, integer DSP; version 1.0 also has minver and nbody FP | Mostly small arrays and code; limited large-memory pressure | Embedded deterministic inputs; CPU_MHZ=1 for this smoke set | Six 1.0 kernels have pinned RV64GC bare recipes. Upstream has embedded RISC-V ports. Embench-DSP is a separate suite and is not qualified here. |
| [LLVM MultiSource](https://github.com/llvm/llvm-test-suite), Apache-2.0 with LLVM exceptions for infrastructure; individual programs retain other licences | Broad C/C++ applications, integer and FP | Parsers, codecs, pointer structures and loops | Small/reference inputs vary by program; no one suite footprint | [CMake cross-compilation and test-suite guide](https://llvm.org/docs/TestSuiteGuide.html); Linux first; not verified. Audit each selected program's licence. |
| [GAP](https://github.com/sbeamer/gapbs), BSD-3-Clause | Graph traversal, integer IDs and FP ranking | Irregular loads, atomics and frontier branches | Generated graphs with fixed seed; propose scale 10 for smoke and 20 for memory studies; external graph licences are separate | C++/OpenMP Linux; start with one thread; not verified. Standard large graphs exceed a small RTL memory image. |
| [Ligra](https://github.com/jshun/ligra), MIT | Graph traversal and ranking | Sparse/dense frontier changes; shared-memory traffic | Fixed generated graph or pinned graph file; size depends on vertices and edges | C++ Linux; use serial configuration first; not verified. Parallel runs are a later tier. |
| [PolyBench/C 4.2.1](https://github.com/ferrandi/PolyBenchC), Ohio State permissive licence in LICENSE.txt | Mostly FP affine loop kernels | Predictable loop branches; strides, reuse and bandwidth | MINI/SMALL/MEDIUM/LARGE/EXTRALARGE dimensions in headers | C with runtime allocation/timing adaptation for bare metal; Linux cross-build route; not verified. It misses parser and pointer-heavy work. |
| [MiBench](https://vhosts.eecs.umich.edu/mibench/source.html), per-benchmark licences | Automotive, networking, security, media and office code | Mixed branch and access patterns | Supplied small/large input files | Portable C with old build scripts; Linux first; not verified. Audit each source and data licence. |
| [SQLite speedtest1](https://sqlite.org/src/file/test/speedtest1.c), [public domain deliverable code](https://sqlite.org/copyright.html) | SQL parser, B-tree operations and integer work | Branch-heavy interpreter, pointer access and page reuse | Propose in-memory DB, size 5 smoke / 100 application tier, fixed test selection and PRAGMAs | RV64 Linux static build route; not verified. Use --verify and pin result content; exclude wall time. |
| [zstd](https://github.com/facebook/zstd), BSD-3-Clause or GPL-2.0 | Compression, entropy coding and integer arithmetic | Match finding and data-dependent branches; window-size pressure | Propose deterministic 64 KiB smoke / 8 MiB text+binary corpora, level 3, one thread | Portable library, Linux CLI; not verified. Validate decompression byte-for-byte. |
| [lz4](https://github.com/lz4/lz4), BSD-2-Clause library; GPL-2.0-or-later CLI | Integer hashing and copy loops | Match branches, sequential input/output and hash tables | Same fixed corpora; default compression level, one thread | Library can use a bare wrapper; Linux CLI route; not verified. Validate decoded bytes. |
| [xz](https://github.com/tukaani-project/xz/blob/master/COPYING), current liblzma/tools 0BSD; some auxiliary files differ | LZMA range coding and dictionaries | Branch-heavy coding and large dictionary reuse | Same corpora; propose -1 smoke, -6 application tier, one thread | RV64 Linux route; not verified. Old release licences differ. Pin the selected release and dictionary size. |
| [gzip](https://www.gnu.org/software/gzip/), GPL-3.0-or-later | Deflate and Huffman coding | Integer branches, sliding windows and copies | Same corpora; -n -6 removes timestamp/name variation | RV64 Linux route; not verified. Compare decoded bytes and deterministic compressed output. |
| [QuickJS](https://bellard.org/quickjs/), MIT | Bytecode interpreter, tagged values, integer and FP | Indirect dispatch, allocation and garbage collection | Pin a self-contained script with fixed iteration count and checksum; no clock/random/network | Portable C, Linux CLI route; not verified. Pin the engine, script and checksum. |
| [Lua](https://www.lua.org/license.html), MIT | Interpreter, tables, integer and FP | Indirect branches, hash lookups and allocation | Pin table/string/numeric scripts, fixed seeds and checksums | Portable C, RV64 Linux route; not verified. Avoid timing output and system libraries. |
| [TinyCC small compiler build](https://github.com/mirror/tinycc), LGPL-2.1 with per-file exceptions | Preprocessing, parsing, symbols and code generation | Branch-heavy code, pointer traversal and allocation | Pin compiler-under-test and a small C project; fix file order and path mapping | Select a revision with a RISC-V backend; build the compiler for RV64 Linux, then compile the pinned project in the guest. Not verified. Host cross-compilation alone is not this workload. |
| [Verilator](https://github.com/verilator/verilator), LGPL-3.0 or Artistic-2.0 | Large C++ parser and code generation | Large code footprint, pointer structures and allocation | Pin a small HDL design and generated-output checker | Linux application tier later; not verified. More dependencies and build cost than TinyCC. |

These licence labels describe upstream files. They do not change the unresolved
repository licence decision (#37). Preserve notices and check each pinned source.

## Pins and default inputs

The manifest selects Embench-IoT commit
`0466a18e4f6b47e19598d7c6ba72916d54b68f65` (embench-1.0).
It pins `riscv64-unknown-elf-gcc (g1b306039a) 15.1.0` and each full argv.
Common flags include `-O2 -march=rv64gc -mabi=lp64d -mcmodel=medany`,
`-fno-common -fno-builtin -ffp-contract=off -DCPU_MHZ=1`.
Fixed `-ffile-prefix-map` values remove absolute source and runtime paths
from assertion strings. No LTO, fast math, profile feedback or vector extension is enabled.
The startup, linker script and checker wrapper are versioned with the runner.
Keep the complete GCC/newlib distribution for repeat experiments. A version line
and executable hash alone do not freeze GCC's linker and sysroot.

| Kernel | Fixed input | Expected result |
|---|---|---|
| crc32 | Upstream pseudo-random sequence, reset seed 0, 1024 samples per local iteration | Upstream checker compares CRC residue to 11433 |
| matmult-int | Upstream fixed matrix dimensions and initialisation | Upstream checker compares the full result matrix |
| slre | Four embedded regular expressions and fixed embedded text | Result 102 |
| nettle-aes | Embedded key, plaintext and expected ciphertext | Upstream encryption/decryption checker |
| minver | Embedded 3x3 float matrix | Upstream tolerance checks on inverse and determinant |
| nbody | Embedded five-body solar system and fixed steps | Upstream tolerance checks on energy, positions, velocities and masses |

All six run the upstream LOCAL_SCALE_FACTOR with CPU_MHZ=1, no warmup,
one `initialise_benchmark` and one `benchmark` call. The wrapper requires
`verify_benchmark(result) == 1`. It then exits 0 through HTIF. Empty stdout
has SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
This is a functional checker policy, not a claim of equal floating-point bits
across host architectures. There is no inferred output baseline from the DUT.

The proposed Linux application tier uses SQLite, zstd and QuickJS first, then
TinyCC and a graph workload. These selections add interpreter, parser, large
window and irregular graph work. Their exact revisions, scripts, input hashes,
reference outputs and native RV64 runs remain required before promotion to a
default. The comparison's proposed sizes are not accepted pins.

## Behaviour and SPEC comparison

Collect dynamic instruction categories from a complete Spike instruction log.
Normalise compressed mnemonics before counting. Separate integer, FP, load,
store, conditional branch and indirect control flow. Categories can overlap:
FP loads count as both FP and loads. Include startup and checker overhead when
reporting whole-program counts. Add ROI markers before making kernel-only claims.
Do not derive dynamic mix from an ELF disassembly.

For branch behaviour, collect taken transitions, indirect target diversity and
branch MPKI under a pinned predictor model. For memory behaviour, collect access
addresses, reuse distance, working-set curves, cache MPKI, TLB misses and bytes
per thousand instructions under pinned cache/page parameters. Instruction
fractions alone cannot establish either branch predictability or locality.
Spike is an ISA oracle. It does not supply hardware predictor/cache miss rates.
Use a pinned gem5 model for trends and C1 RTL counters for hardware results.

[Limaye and Adegbija, ISPASS 2018](https://tosiron.com/papers/2018/SPEC2017_ISPASS18.pdf)
study instruction mix, IPC, branch and cache behaviour across SPEC CPU2017.
[Singh and Awasthi, ICPE 2019](https://research.spec.org/icpe_proceedings/2019/proceedings/p285.pdf)
study instruction volume, memory footprint and bandwidth. Their reported
instruction volume makes full RTL runs impractical. The small embedded default
has short code paths and small fixed arrays. It underrepresents large code,
large working sets, filesystem paths and long phase changes. This is a
source-based limitation, not a measured SPEC correlation.
Do not compare x86 opcode fractions or miss rates directly with RV64 fractions.
A quantitative comparison needs matching metric definitions, compiler policy,
input scale, cache/predictor parameters and phase boundaries. No SPEC-relative
performance ratio or parity claim follows from this set.

## SimPoint-style sampling plan

1. Run each full input on an ISA oracle first. Check its full output. Record
   source, ELF, input, compiler and oracle hashes. Use one hart and fixed seeds.
2. Produce basic-block vectors for consecutive intervals of 10 million retired
   user instructions. Exclude OS and startup with explicit ROI markers.
   Keep a shorter final interval with its actual instruction weight.
3. Cluster normalised vectors with fixed seed 1. Sweep k=1..30 and retain the
   smallest k at the chosen distance threshold. Use the nearest actual interval
   as each representative. Record the clustering tool/version and all vectors.
4. Store each interval's start instruction, length and weight. Weights equal
   represented instructions divided by full ROI instructions and sum to 1.
   Keep rare high-miss phases even when their weight is small.
5. For each sample, fast-forward functionally to a checkpoint before the ROI.
   Restore architectural registers, CSRs, memory and devices. Warm the selected
   cache and predictor model for 1 million instructions. Then measure the
   10-million-instruction interval. State exactly which state is restored.
6. Compare the weighted estimate with full runs on the short inputs. Report
   weighted CPI as sum(weight * cycles/instructions), then invert for IPC.
   Do not average IPC directly. Report dispersion and warmup sensitivity.
7. Run RTL only after a checkpoint/import path has demonstrated equal committed
   instruction streams and memory at the sample boundary. Otherwise replay from
   reset through warmup. Do not call a Spike register dump an RTL checkpoint.

This is a plan. Automatic BBV capture, clustering, device checkpoints and RTL
restore are not implemented. No sampled result is currently a full-run result.
