# RV64 PMP elaboration limits

Core revision: `9f70315deb3390b283995c5b8f1bd38215ecf52b`.
SpinalHDL revision: `de72faf6062206a89b445e5cc07e32ed982712c8`.

The pinned core rejects 4-byte PMP granularity on RV64. Its assertion states
that it cannot check both halves of an 8-byte access at that granularity.
This is an explicit core limit.

The same configuration with 8-byte granularity fails elaboration with nine
errors. `PhaseCheck_noLatchNoOverride` reports `ASSIGNMENT OVERLAP` for the
one-bit UInt created in `memory/PmpPlugin.scala:174`.

Minimal parameter set:

```scala
val p = new vexiiriscv.ParamSimple()
p.xlen = 64
p.addISA("m", "a", "s", "u")
p.pmpParam.pmpSize = 8
p.pmpParam.granularity = 8
p.fixIsaParams()
val plugins = p.plugins()
vexiiriscv.ParamSimple.setPma(plugins)
spinal.core.SpinalConfig().generateVerilog(vexiiriscv.VexiiRiscv(plugins))
```

The failing constructor uses `U(granularityWidth-2 bits, default -> isNapot,
granularityWidth-3 -> (address.lsb && isNapot))`. At 8-byte granularity, both
assignments cover the complete one-bit value. This explains the elaboration
error. It is not an RTL execution finding.

The suite configuration now requests 16-byte granularity. It does not patch
the core, disable overlap checks or claim support for 4-byte or 8-byte regions.
The failed regression attempts have zero RTL runs. Their 180 setup errors
must not be counted as executed DUT failures.
