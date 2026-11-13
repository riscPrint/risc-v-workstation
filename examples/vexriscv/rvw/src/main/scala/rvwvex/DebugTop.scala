package rvwvex

import spinal.core._
import spinal.lib._
import spinal.lib.cpu.riscv.debug._
import vexriscv.{VexRiscv, VexRiscvConfig}
import vexriscv.plugin._

/** Debug configurations of the example core. Additive: `rv32im` stays unchanged.
  * `rv32im_dmi` exposes the SpinalHDL Debug Module bus as top-level `dmi_*` ports.
  * `rv32im_jtag` adds the upstream `EmbeddedRiscvJtag` DTM with top-level `jtag_*` pins.
  * Both use the CSR plugin's official debug support (Debug 0.13, two execute triggers). */
object VexDebug {
  val configs = Seq("rv32im_dmi", "rv32im_jtag", "rv32im_trace")

  def configuration(config: String): VexRiscvConfig = config match {
    case "rv32im" => VexTop.configuration()
    case c if VexCached.configs.contains(c) => VexCached.configuration(c)
    case "rv32im_trace" => VexRiscvConfig(plugins = VexTop.configuration().plugins :+ new TraceIngressPlugin)
    case "rv32im_dmi" | "rv32im_jtag" =>
      val plugins = VexTop.configuration().plugins.map {
        case _: CsrPlugin => new CsrPlugin(VexTop.csrConfig.copy(withPrivilegedDebug = true))
        case p => p
      }
      val debug = if (config == "rv32im_dmi") new DmiPortPlugin
        else new JtagDebugPlugin(DebugTransportModuleParameter(addressWidth = 7, version = 1, idle = 7))
      VexRiscvConfig(plugins = plugins :+ debug)
  }
}

/** The Debug Module with its DMI bus as a top-level slave port. */
class DmiPortPlugin extends Plugin[VexRiscv] {
  var dmi: DebugBus = null
  var ndmreset: Bool = null

  override def setup(pipeline: VexRiscv): Unit = {
    dmi = slave(DebugBus(7)).setName("dmi")
    ndmreset = out(Bool()).setName("ndmreset")
  }

  override def build(pipeline: VexRiscv): Unit = {
    val dm = DebugModule(DebugModuleParameter(version = 2, harts = 1, progBufSize = 2, datacount = 1,
      hartsConfig = List(DebugModuleCpuConfig(xlen = 32, flen = 0, withFpuRegAccess = false))))
    ndmreset := dm.io.ndmreset
    dm.io.ctrl <> dmi
    val privBus = pipeline.service(classOf[CsrPlugin]).debugBus.setAsDirectionLess()
    privBus <> dm.io.harts(0)
    privBus.dmToHart.removeAssignments() <-< dm.io.harts(0).dmToHart
  }
}

/** Upstream JTAG DTM and Debug Module, clocked by the core clock domain. */
class JtagDebugPlugin(p: DebugTransportModuleParameter) extends EmbeddedRiscvJtag(p, withTap = true) {
  override def setup(pipeline: VexRiscv): Unit = {
    debugCd = ClockDomain.current
    super.setup(pipeline)
  }
}
