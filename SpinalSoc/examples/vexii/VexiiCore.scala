package examplesocvexii

import spinal.core._
import spinal.core.fiber._
import spinal.lib._
import spinal.lib.bus.amba4.axi._
import vexiiriscv.{ParamSimple, VexiiRiscv}
import vexiiriscv.fetch.FetchCachelessAxi4Plugin
import vexiiriscv.execute.lsu.LsuCachelessAxi4Plugin
import vexiiriscv.misc.PrivilegedPlugin
import rvwsoc.AxiCoreWrapper
import spinal.lib.bus.misc.SizeMapping
import spinal.lib.bus.tilelink.{M2sTransfers, SizeRange}
import spinal.lib.system.tag.PmaRegionImpl

/** Compile with the pinned VexiiRiscv Spinal source dependencies, not release jars. */
class VexiiCore extends Component with AxiCoreWrapper {
  val config = Axi4Config(32, 32, 8, useLen = false, useBurst = false,
    useLock = false, useQos = false, useRegion = false)
  val io = new Bundle {
    val bus = master(Axi4(config))
    val interrupts = in Bits(32 bits)
    val debugReset = in Bool()
    val retired = out UInt(32 bits)
  }
  def bus = io.bus
  def interrupts = io.interrupts
  def debugReset = io.debugReset
  val parameter = new ParamSimple()
  parameter.xlen = 32
  parameter.addISA("m")
  parameter.fixIsaParams()
  val plugins = parameter.plugins()
  plugins += new FetchCachelessAxi4Plugin()
  plugins += new LsuCachelessAxi4Plugin()
  // These windows match this example's composed map, including low-address MMIO.
  val windows = Seq((0x80000000L, 0x10000L, true), (0x10000000L, 0x100L, false),
    (0x02000000L, 0x10000L, false), (0x0c000000L, 0x400000L, false),
    (0x10001000L, 0x100L, false))
  ParamSimple.setPma(plugins, windows.map { case (base, size, main) =>
    PmaRegionImpl(mapping = SizeMapping(base, size), isMain = main,
      isExecutable = main, transfers = M2sTransfers(get = SizeRange.all, putFull = SizeRange.all))
  })
  val area = new ClockingArea(ClockDomain.current.copy(reset = ClockDomain.current.readResetWire || io.debugReset)) {
    val cpu = VexiiRiscv(plugins)
    val wiring = Fiber build new Area {
      val instruction = cpu.host[FetchCachelessAxi4Plugin].logic.bridge.axi
      val data = cpu.host[LsuCachelessAxi4Plugin].logic.axi.toShared()
      val arbiter = Axi4SharedArbiter(config, 1, 0, 1, 2)
      arbiter.io.readInputs(0) << instruction.arValidPipe()
      arbiter.io.sharedInputs(0) << data
      io.bus << arbiter.io.output.toAxi4()
      val privileged = cpu.host[PrivilegedPlugin].logic
      privileged.harts(0).int.m.timer := io.interrupts(7)
      privileged.harts(0).int.m.software := io.interrupts(3)
      privileged.harts(0).int.m.external := io.interrupts(11)
      privileged.rdtime := 0
      val commitMask = cpu.rework {
        out(CombInit(privileged.harts(0).commitMask)).setName("soc_commit_mask")
      }
      val retired = Reg(UInt(32 bits)) init(0)
      retired := retired + CountOne(commitMask).resized
      io.retired := retired
    }
  }
}
object VexiiElaborate extends App {
  SpinalConfig(targetDirectory = "rtl/vexii-soc").generateVerilog(new VexiiCore)
}
