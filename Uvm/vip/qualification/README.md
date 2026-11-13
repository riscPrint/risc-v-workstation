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
Verilator 5.052 compiled all 20 fixtures. All 16 runnable fixtures passed
every declared good and fault case at seeds 1, 2 and 3: 120 checked runs.
DRAM, Ethernet, PCIe and RNM still have inert SV model stubs. Their compile
results do not establish native-model or runtime support. AXI4-Lite has no
separate SV runtime result in this campaign.

The first pass qualified 13 fixtures. AXI, TileLink and UART registered
reactive components with the UVM root, then also called their phases manually.
The scheduler started them again. The corrected fixtures let UVM invoke each
phase once. UART configures transmit observation before build. Root fatal
actions also cover object-level errors, which previously could exit zero.

The AHB malformed-manager fixture now holds the subordinate for two wait
cycles. Its stability assertion sees the injected address change before the
burst monitor accepts that address. The expected diagnostic stays
`AHB_ADDRESS_STABLE`. Scoreboard comparisons, traffic checks and expected
fault diagnostics are unchanged. The initial failures were fixture issues.
They do not establish a Verilator language limitation.

The published JSON uses `$REPO` and `$VEXRISCV` path aliases. Source hashes,
exit codes and check outcomes stay unchanged. The private reports retain
literal commands and paths. Use `report.py --path-alias PATH=TOKEN` to publish
another local campaign. Accellera DPI and HDL backdoors remain outside this
`UVM_NO_DPI` profile. No physical or commercial VIP qualification follows.

Local evidence is under `$VEXRISCV/uvm-runs/` in `sv-vip-qualification`,
`sv-vip-recheck`, `sv-vip-phase-once` and `sv-vip-ahb-stability`.
