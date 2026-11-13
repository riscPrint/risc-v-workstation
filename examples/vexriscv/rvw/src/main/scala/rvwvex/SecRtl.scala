package rvwvex

import spinal.core._
import vexriscv.{VexRiscv, VexRiscvConfig}
import vexriscv.plugin._

/** Plain Verilog for `rvw sec` native runs. `rv32im` is the example configuration with probes.
  * `rv32imu` adds user mode (CsrPlugin userGen) for isolation runs across a privilege switch.
  * Usage: SecRtl OUT [rv32im|rv32imu]... */
object SecRtl {
  def configuration(variant: String): VexRiscvConfig = {
    val base = VexTop.configuration()
    variant match {
      case "rv32im" => base
      case "rv32imu" => VexRiscvConfig(plugins = base.plugins.map {
        case c: CsrPlugin => new CsrPlugin(c.config.copy(userGen = true))
        case p => p
      })
      case other => sys.error(s"unknown sec variant $other")
    }
  }

  def main(args: Array[String]): Unit = {
    val variants = if (args.length > 1) args.drop(1).toSeq else Seq("rv32im", "rv32imu")
    for (variant <- variants) spinalprobes.Probe.enabled(true) {
      VexTop.spinalConfig.copy(targetDirectory = s"${args(0)}/$variant").generateVerilog(
        new VexRiscv(configuration(variant)).setDefinitionName("VexTop"))
    }
  }
}
