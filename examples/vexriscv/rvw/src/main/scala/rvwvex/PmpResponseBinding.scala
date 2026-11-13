package rvwvex

import spinal.core._
import vexriscv.VexRiscv
import vexriscv.plugin.PmpPluginNapot

/** Bind the PMP-only example's address-translation response metadata.
  * The upstream cacheless PMP plugin omits these two response fields.
  * Permission outputs remain upstream logic. No source checkout is patched. */
class PmpResponseBinding extends PmpPluginNapot(4, 32, _ => False) {
  override def build(pipeline: VexRiscv): Unit = {
    super.build(pipeline)
    val path = java.nio.file.Path.of(sys.env("RVW_HOME"),
      "examples/vexriscv/rvw/sec/pmp-response.json")
    val binding = ujson.read(java.nio.file.Files.readString(path))
    require(binding("schema").str == "rvw.vex-pmp-response/1")
    require(binding("variant").str == "rv32imu-pmp")
    pipeline.rework {
      iPort.bus.rsp.bypassTranslation := Bool(binding("instruction_bypass_translation").bool)
      dPort.bus.rsp.bypassTranslation := Bool(binding("data_bypass_translation").bool)
    }
  }
}
