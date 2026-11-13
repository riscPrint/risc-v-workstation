# Base environment and register support

`rvw_base_pkg.sv` supplies the ordered transaction scoreboard and base test.
`rvw_ral_pkg.sv` supplies normalized register transfers, an adapter, a typed
predictor, and wrappers for the standard UVM reset, bit-bash and access
sequences. Register classes still come from `rvw regress uvm-ral` or the
bench manifest's `register_map` field.

The project bus driver translates each `register_transfer` and returns read
data and `status`. The default status is `UVM_NOT_OK`. A missing bus response
cannot silently predict success. Connect the bus monitor to `predictor.bus_in`.
Set `predictor.map` and `predictor.adapter`. Set map auto-prediction to zero
when a predictor is connected. Do not predict the same access twice.

Reset the DUT before `reset_check`. The stock reset sequence resets the
model; the project owns physical reset. `bit_bash` uses the generated access
policies. Exclude side-effect registers according to the project's plan.
`access_check` requires real backdoor access. It reports
`UNSUPPORTED_RAL_BACKDOOR` when a register has neither a custom backdoor nor
an HDL path. HDL paths still require a simulator HDL backend. Verilator with
`UVM_NO_DPI` needs a custom `uvm_reg_backdoor`.

`../examples/ral/bench.json` exercises generated four-word RAL through an
adapter and predictor. It uses a fixture backdoor for standard access tests.
The memory resides in the fixture driver. This verifies UVM RAL plumbing,
not a physical peripheral or a protocol bus implementation.
