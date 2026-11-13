# Python agent RTL qualification

These tests drive real RTL through the Python cocotb adapters. They do
not build UVM. Run each command from the repository root with `nice -n 10`.
Use a new output directory for each run.

```sh
rvw/.venv/bin/python Uvm/vip/rtl/smoke.py --protocol spi --out /tmp/spi-new
rvw/.venv/bin/python Uvm/vip/rtl/smoke.py --protocol uart --out /tmp/uart-new
rvw/.venv/bin/python Uvm/vip/rtl/smoke.py --protocol i2c --out /tmp/i2c-new
rvw/.venv/bin/python Uvm/vip/rtl/smoke.py --protocol gpio --out /tmp/gpio-new
rvw/.venv/bin/python Uvm/vip/rtl/smoke.py --protocol axi --out /tmp/axi-new
rvw/.venv/bin/python Uvm/vip/rtl/smoke.py --protocol tilelink --out /tmp/tl-new
```

The runner uses Icarus and cocotb 2.0.1. Each campaign runs seed 17 against
good and bad RTL. It requires zero good-DUT failures and the exact expected
data or IRQ diagnostic for bad RTL. It rejects a campaign over one minute.
The expected failing simulation in each campaign is deliberate.

SPI uses digital wire loopback. UART preserves framing and changes one
data bit in the bad DUT. I2C ACKs bytes and changes ACK to NACK in the bad
DUT. GPIO uses two synchronization registers and changes one IRQ bit.
AXI and TileLink check four single-beat reads with address-derived data.
They do not qualify bursts, writes, coherence or exclusive operations.
The AXI fixture uses the full AXI4 pin profile. AXI4-Lite uses the same RTL with the Lite adapter and is checked separately. Good/bad outcomes establish adapter-to-RTL execution only.

APB, AHB and AXI-Stream have their existing campaigns:

```sh
rvw/.venv/bin/python Uvm/vip/apb/cocotb_smoke.py --out /tmp/apb-new
rvw/.venv/bin/python Uvm/vip/ahb/cocotb_smoke.py --out /tmp/ahb-new
rvw/.venv/bin/python Uvm/vip/axis/cocotb_smoke.py --out /tmp/axis-new
```

These use Verilator and three seeds with good and bad RTL. They also
compile no UVM package. See each protocol README for its fixture scope.

## Semantic endpoint adapters

See [the measured semantic endpoint matrix](CONTRACT_RESULTS.md) for PCIe,
Ethernet, the DRAM contract and the reduced coherent agent. These use the
existing Python request APIs through cocotb with bounded RTL endpoints.
They do not replace native vendor models or qualify physical links.

```sh
rvw/.venv/bin/python Uvm/vip/rtl/contracts_smoke.py --protocol pcie --out /tmp/pcie-new
```

Select `ethernet`, `dram` or `coherent` for the other profiles. Each build
runs good and corrupt RTL at seed 17 and keeps the XML and source hashes.
