# SV protocol runtime campaign

Run from the repository root. Use a new output path.

```sh
scripts/with-lock.sh vex-uvm nice -n 10 rvw/.venv/bin/python \
 Uvm/vip/qualification/run.py --out /tmp/sv-vip-new --build-timeout 1800
rvw/.venv/bin/python Uvm/vip/qualification/report.py \
 /tmp/sv-vip-new/matrix.json /tmp/sv-vip-new/matrix.md
```

Each agent gets one Verilator build. The campaign reuses the protocol's
existing smoke matrix at seeds 1, 2 and 3. It keeps build commands, source
hashes, simulator version, exit codes, timeouts and per-case logs.
The pinned Accellera archive is checked by the existing UVM unpacker.
Use `--archive` for an existing archive. Use `--agents apb ahb` to select
agents. The default selects all 20 SV protocol directories.

A compile result is separate from runtime checks. An empty model bridge
has no good/bad runtime evidence. A timeout, missing completion or wrong
fatal diagnostic remains incomplete. No generic simulator limitation is
inferred from a failed fixture. Read the recorded build or runtime error.

The report keeps corrupt-DUT checks separate from malformed-manager checks.
A failed manager check cannot qualify that case. A corrupt-DUT result applies
only to the exact corruption and fixture used by that agent.

## Native results on 2026-11-13

See [the measured matrix](native-2026-11-13.md) and
[its commands, source hashes and per-case results](native-2026-11-13.json).
Verilator 5.052 compiled all 20 agents. Thirteen fixtures passed all normal
good-DUT seeds and all corrupt-DUT seeds. APB's reset-abort rerun also passed.
The original and fixed-source APB runs remain separate in local evidence.

The remaining runtime limits on this engine are:

- AXI stops on `AXI_B_WITHOUT_WRITE` in good runs. The fixture emits a B
  response while the monitor has only two W beats for a four-beat request.
  `+trace_channels` records the sampled channels and queue sizes. AXI4-Lite
  has no separate runtime result in this campaign.
- TileLink stops on `TL_MEMORY_DATA` in good runs. Its malformed-manager
  item stops through the global UVM reporter with exit zero. This does not
  meet the negative control's required nonzero exit.
- UART stops on `UART_BYTE_STREAM` in both good and corrupt runs. The same
  fatal in both runs cannot establish corruption detection.
- AHB detects corrupt read data, but the malformed manager stops on
  `AHB_BURST_ADDRESS` before the expected `AHB_ADDRESS_STABLE` diagnostic.
  That assertion case remains unqualified.
- DRAM, Ethernet, PCIe and RNM compile, but their SV fixtures have no native
  model, UVM test, completion check or corrupt-DUT checker. They time out.

These are observed runtime gaps on the recorded Verilator configuration.
The logs do not establish that each gap is a Verilator implementation bug.
No generic engine limitation is used to waive a failed checker. Accellera
DPI, HDL backdoors and physical models remain outside this `UVM_NO_DPI` run.

Local logs are under `$VEXRISCV/uvm-runs/sv-vip-qualification/` and
`$VEXRISCV/uvm-runs/sv-vip-recheck/` in the private `uvm` core copy.

Paths in `native-2026-11-13.json` use `$CHECKOUT` for the workstation checkout and
`$RUN_ROOT` for the local run directory, so the file holds no personal paths.
The published JSON replaces local absolute paths with `$REPO` and
`$VEXRISCV`. `report.py --path-alias PATH=TOKEN` makes those aliases.
The private raw reports retain the original executable commands and paths.
Source hashes, exit codes and check outcomes stay unchanged.
