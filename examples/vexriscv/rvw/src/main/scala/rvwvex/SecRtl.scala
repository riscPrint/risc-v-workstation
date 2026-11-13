package rvwvex

import spinal.core._
import vexriscv.{VexRiscv, VexRiscvConfig}
import vexriscv.plugin._

/** Plain Verilog for `rvw sec` native runs. `rv32im` is the example configuration with probes.
  * `rv32imu` adds user mode (CsrPlugin userGen) for isolation runs across a privilege switch.
  * `rv32imu-pmp` adds a 4-region NAPOT PMP (32-byte granularity) on fetch and data accesses.
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
      case "rv32imu-pmp" => VexRiscvConfig(plugins = configuration("rv32imu").plugins.flatMap {
        // Route fetch and data accesses through a 4-region PMP. The bus parameters stay the same.
        case _: IBusSimplePlugin => Seq(new IBusSimplePlugin(resetVector = 0x80000000L, cmdForkOnSecondStage = false,
          cmdForkPersistence = true, prediction = STATIC, catchAccessFault = true, compressedGen = false,
          memoryTranslatorPortConfig = MmuPortConfig(portTlbSize = 4)))
        case _: DBusSimplePlugin => Seq(new DBusSimplePlugin(catchAddressMisaligned = true, catchAccessFault = true,
          memoryTranslatorPortConfig = MmuPortConfig(portTlbSize = 4)),
          new PmpResponseBinding)
        case p => Seq(p)
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
