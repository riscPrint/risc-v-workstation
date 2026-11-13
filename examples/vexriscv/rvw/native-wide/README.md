# Packed ports and whole-core native comparison

`rvw.sim.native_models.Model` accepts packed ports through 65,536 bits. Both
Arcilator and Verilator preserve every bit. Scalar names still identify ports.
`Model(..., wave=PATH)` writes a two-state VCD of public ports. Each timestamp
is one `eval()` call. The 1 ps VCD unit is a display unit, not physical timing.
No internal signal or four-state wave coverage is claimed.

The native wide-port regression checks widths 31, 32, 63, 64, 65, 129 and 257.
It requires the same seeded register updates from both engines and identical
public-port waves. Run it with the pinned CIRCT installation and Verilator:

```sh
nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/test_native_wide_models.py -q
```

The project engine probe accepts `--wave`. The campaign runs the same captured
VexRiscv RTL and ELF on both engines in alternating order. It requires complete
C2 byte equality across every run. The first pair captures waves. Later pairs
measure execution without wave capture. Build time stays separate. Execution
time includes the Python buses, retirement capture and C2 write/validation.

```sh
riscv64-unknown-elf-gcc -march=rv32im_zicsr -mabi=ilp32 -nostdlib \
  -T examples/vexriscv/rvw/programs/link.ld \
  examples/vexriscv/rvw/native-wide/loop.S -o /tmp/native-loop.elf
scripts/with-lock.sh vex-simsrv nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/rvw/native-wide/campaign.py --rtl /path/to/VexTop.v \
  --elf /tmp/native-loop.elf --out /tmp/new-comparison
```

Use RTL captured from the selected core revision. `engine-ports.json` supplies
this project's port bindings. These samples are bounded native RTL runs. They
do not establish C4 acceptance or a general engine speed ranking.

Native sample on 2026-11-13 used private core revision
`a62c145aa042a5de874344e0a7683bd7c8c8c870`. All six runs passed with 15,007
retirements and 40,307 cycles. Every complete C2 digest matched. The two
wave files were also byte-identical, at about 13 MiB each. Without waves,
median throughput was 4,332 instructions/s for Arcilator and 5,015 for
Verilator. The ratio was 0.864. Arcilator was slower on this workload.
These are end-to-end native adapter measurements on macOS arm64. They are
not isolated generated-code kernel measurements. See [the sample](results.json).
