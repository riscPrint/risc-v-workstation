# Native semantic RTL endpoint results

On 2026-11-13 the opt-in native test returned 4 passed and 0 skipped.
Each test compiled its endpoint once. It ran seed 17 against good and
corrupt RTL. The negative simulation must fail on the exact listed check.
The runner requires an executed test case and rejects skipped or empty XML.
Engine: Icarus Verilog 14.0 devel. Cocotb: 2.1.0.

| Agent | Good endpoint | Corrupt endpoint | Required diagnostic |
|---|---|---|---|
| PCIe semantic adapter | pass | detected | PCIE_COMPLETION_DATA |
| Ethernet MAC-client adapter | pass | detected | ETH_TX_DATA_OR_ERROR |
| DRAM functional contract | pass | detected | DRAM_MODEL_DATA |
| Reduced coherent manager | pass | detected | COH_DATA |

PCIe checks enumeration, command enable and four eight-byte writes/reads.
It does not encode TLPs or check link training, DMA or completion reordering.
Ethernet checks four eight-byte transmit and receive packets. Its host buffer
comes from RTL observations. Descriptor semantics use the project's bridge.
It does not implement a MAC, FCS or PHY. The bad endpoint corrupts transmit
readback. Receive corruption has no separate negative control in this matrix.
DRAM checks one bank, an ACT, four writes/reads and PRE. It uses functional
mode. It does not qualify JEDEC timing or an external vendor model.
The coherent endpoint checks one line, ReadUnique and WriteBack with eight
completions. It does not qualify snoop routing, concurrent requests or CHI.

The existing Python agent supplies each request through a cocotb bridge.
The RTL holds the independently observed memory or line value. The checker
compares the actual response with its own model. No expected response is
substituted for an RTL response.

```sh
RVW_UVM_CONTRACTS_NATIVE=1 nice -n 10 rvw/.venv/bin/python \
 -m pytest rvw/tests/test_vip_contracts_native.py -q
```

Local evidence is under `$VEXRISCV/uvm-runs/contracts-native-current/`.
Each campaign keeps good/bad JUnit files and `results.json` with source hashes.
These are cocotb agent checks. They do not establish SV UVM runtime support.

See [the result and source hashes](native-2026-11-13.json) for the final rerun.
