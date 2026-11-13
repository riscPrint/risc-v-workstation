package rvwvexii

import spinal.core._
import spinal.lib._
import spinal.lib.com.jtag.Jtag
import spinal.lib.cpu.riscv.debug._
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.misc.PrivilegedPlugin

/** Extra example configurations. Uses the upstream privileged-debug bus. */
class DebugPortPlugin(withJtag: Boolean) extends FiberPlugin {
  val logic = during build new Area {
    val dm = DebugModule(DebugModuleParameter(version = 2, harts = 1, progBufSize = 2,
      datacount = 1, hartsConfig = List(DebugModuleCpuConfig(xlen = 32, flen = 0, withFpuRegAccess = false))))
    val ndmreset = out(Bool()).setName("ndmreset")
    ndmreset := dm.io.ndmreset
    if (withJtag) {
      val jtag = slave(Jtag()).setName("jtag")
      val dtm = DebugTransportModuleJtagTap(DebugTransportModuleParameter(addressWidth = 7, version = 1, idle = 7),
        debugCd = ClockDomain.current)
      dm.io.ctrl <> dtm.io.bus
      dtm.io.jtag <> jtag
    } else {
      val dmi = slave(DebugBus(7)).setName("dmi")
      dm.io.ctrl <> dmi
    }
    val bus = host[PrivilegedPlugin].logic.harts(0).debug.bus.setAsDirectionLess()
    bus <> dm.io.harts(0)
    bus.dmToHart.removeAssignments() <-< dm.io.harts(0).dmToHart
  }
}
