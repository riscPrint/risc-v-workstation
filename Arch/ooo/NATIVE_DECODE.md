# Native full-run decoding

The flat C2/1 reader now decodes supported IMC instructions in C. It packs
scheduler arrays without a Python callback for each new instruction word.
Unsupported classes use the existing Python template decoder. Old native
libraries keep that callback path. The shared C2 validator remains the fallback.

The [benchmark](benchmark-decode.py) includes file reads, validation, packing,
scheduling and hashes. It excludes generation and compilation. Each stream
has 500,000 instructions. Each variant gets one warmup and four alternating
trials. Every trial checks equal cycles, IPC, events, occupancy and top-down
counts. These synthetic traces do not validate architectural execution.

| Stream | Control instr/s | Native decode instr/s | Wall speedup |
|---|---:|---:|---:|
| Cached integer | 590,617 | 518,985 | 0.879x |
| Diverse integer | 62,994 | 483,155 | 7.670x |
| Diverse components | 53,633 | 282,968 | 5.276x |

The cached stream regressed in elapsed time. Its CPU rates were 1.810 million
and 1.792 million instructions per CPU-second. Diverse integer CPU rates
were 0.230 million and 1.695 million. Diverse component CPU rates were
0.239 million and 1.269 million. The host ran other workers. Wall-time
variation limits the comparison. CPU time includes the hashing thread.

The full-run millions/s target is not met in wall time. Native decoding
removes the callback cost on these IMC inputs. It does not remove file I/O,
validation, hashing or the Python fallback for other instructions.
See [all trials and hashes](benchmark-results-decode.json).
