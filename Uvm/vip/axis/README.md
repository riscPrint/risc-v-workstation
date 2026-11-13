# AXI4-Stream agents

This profile follows [Arm IHI 0051A](https://documentation-service.arm.com/static/642583d7314e245d086bc8c9).
It uses 32-bit data, 4-bit TKEEP/TSTRB, TLAST, 2-bit TID/TDEST and 4-bit
TUSER. Each byte has one user bit. It supports sparse byte qualifiers,
position bytes, empty packets and packet interleaving by stream identity.
AXI5-Stream wakeup and check signals are outside this profile.

## UVM

Compile `axis_if.sv` before `axis_pkg.sv`. Use the pinned Accellera package
from [the UVM guide](../../README.md). Define `UVM_NO_DPI`. Enable timing,
assertions and coverage. Set config DB `bus` as `virtual axis_if`.
Instantiate `axis_checker` on each interface. The default active `agent`
creates a source sequencer/driver. Set config DB bit `subordinate_role`
for a seeded sink READY driver. A passive agent creates only its monitor.

The monitor publishes accepted beats through `m.ap`. It checks for missing
TLAST at end of test. It keeps independent packet state for each TID/TDEST.
Connect input and output monitors to `scoreboard.input_port` and
`scoreboard.output_port`. The scoreboard compares semantic byte tokens in
order per stream. Null bytes are discarded. Position bytes carry position
and user information. TLAST emits a separate packet boundary token.
The scoreboard permits cross-stream reordering and null byte suppression.
It does not require invalid TDATA bytes to match.
Call `reset_model()` when your DUT resets.

`directed` covers all keep masks, position bytes, user bits and two
interleaved streams. `random_sequence` sends 32 randomized packets.
`error_sequence` sends four beats for a stalled-data fault. Set driver
`inject_data` and sink `hold` to run that fault. The FIFO's `+buggy` variant
changes data bytes. The interface checker tests stalled stability, byte
qualifier legality and reset VALID. The monitor covers keep/strb/user,
ID/destination, TLAST and routing crosses. It counts stalls separately.

Run the supplied native UVM campaign with:

```sh
nice -n 10 rvw/.venv/bin/python Uvm/vip/axis/smoke.py --out /tmp/axis-new
```

It enforces the Accellera archive pin and a 120-second compile limit.
Good runs must finish with the expected marker. Faults must fail with their
specific diagnostic. UVM runtime qualification remains open. Verilator
lint is separate from runtime evidence.

## Python and cocotb

`rvw.vip.axis` provides `Manager`, `Subordinate`, `Monitor`, `Scoreboard`,
`Fifo`, `sequences` and `inject`. `Monitor` has packet and beat callbacks.
The packet callback receives semantic tokens. Connect source packets to
`Scoreboard.expect` and output packets to `Scoreboard.observe`.
Call both monitors' `finish()` and the scoreboard's `finish()` after drain.
Missing packets and an empty test cannot produce a pass.
Reset samples discard partial packets. Reset the scoreboard separately.

`CocotbAgent` uses an interface prefix and external `clk` and `reset_n`.
The pins are `PREFIX_tvalid`, `PREFIX_tready`, `PREFIX_tdata`,
`PREFIX_tkeep`, `PREFIX_tstrb`, `PREFIX_tlast`, `PREFIX_tid`,
`PREFIX_tdest` and `PREFIX_tuser`. Start `run_monitor()` once per interface.
Use `await send(Beat(...))` for the source. Start `run_subordinate(seed)`
for a seeded sink. The source never waits for READY before it asserts VALID.
Signals change on falling edges. Monitors sample before rising-edge RTL
updates. The pure cycle classes do not need cocotb at import.

Install `cocotb==2.0.1` in the rvw environment. Run the small RTL campaign:

```sh
nice -n 10 rvw/.venv/bin/python Uvm/vip/axis/cocotb_smoke.py --out /tmp/axis-cocotb-new
```

The campaign runs three seeds against a one-entry elastic FIFO, then three
corrupt FIFO runs. Corruption must fail with `AXIS_PACKET_DATA_ORDER`.

## Decisions and limits

Packet drain is a test obligation. AXI-Stream itself does not impose a
maximum packet length or a maximum stall count. The source has a test
policy timeout. The scoreboard preserves per-byte user bits and positions;
other TUSER layouts need a project adapter. It does not model a packet
transformer. Four-state X checking and AXI5-Stream need separate work.
These component checks do not establish SoC conformance.

## Bounded Python RTL evidence

The Python cocotb adapter passed a seeded good RTL test and detected the
controlled bad RTL result. See `Uvm/vip/rtl/README.md` for commands and
fixture scope. This does not establish full protocol conformance or UVM
runtime qualification.
