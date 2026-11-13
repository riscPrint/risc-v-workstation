package examplesocvex

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba4.axi._
import vexriscv.{VexRiscv, VexRiscvConfig}
import vexriscv.plugin._
import rvwsoc.AxiCoreWrapper

/** Project-owned RV32IM wrapper. No cache, MMU, supervisor mode or debug unit. */
class VexCore extends Component with AxiCoreWrapper {
  val config = DBusSimpleBus.getAxi4Config().copy(useId = true, idWidth = 1)
  val io = new Bundle {
    val bus = master(Axi4(config))
    val interrupts = in Bits(32 bits)
    val debugReset = in Bool()
    val retired = out UInt(32 bits)
  }
  def bus = io.bus
  def interrupts = io.interrupts
  def debugReset = io.debugReset
  val area = new ClockingArea(ClockDomain.current.copy(reset = ClockDomain.current.readResetWire || io.debugReset)) {
    val cpu = new VexRiscv(VexRiscvConfig(plugins = List(
      new IBusSimplePlugin(resetVector = 0x80000000L, cmdForkOnSecondStage = false,
        cmdForkPersistence = true, prediction = STATIC, catchAccessFault = true, compressedGen = false),
      new DBusSimplePlugin(catchAddressMisaligned = true, catchAccessFault = true),
      new DecoderSimplePlugin(catchIllegalInstruction = true),
      new RegFilePlugin(regFileReadyKind = vexriscv.plugin.SYNC, zeroBoot = false),
      new IntAluPlugin,
      new SrcPlugin(separatedAddSub = false, executeInsertion = true),
      new FullBarrelShifterPlugin,
      new HazardSimplePlugin(bypassExecute = true, bypassMemory = true, bypassWriteBack = true,
        bypassWriteBackBuffer = true, pessimisticUseSrc = false, pessimisticWriteRegFile = false,
        pessimisticAddressMatch = false),
      new MulSimplePlugin, new DivPlugin,
      new CsrPlugin(CsrPluginConfig.all2(0x80000000L).copy(userGen = false, supervisorGen = false,
        misaExtensionsInit = 0x1100, misaAccess = CsrAccess.READ_ONLY, ebreakGen = true,
        sscratchGen = false, stvecAccess = CsrAccess.NONE, sepcAccess = CsrAccess.NONE,
        scauseAccess = CsrAccess.NONE, sbadaddrAccess = CsrAccess.NONE,
        scycleAccess = CsrAccess.NONE, sinstretAccess = CsrAccess.NONE,
        satpAccess = CsrAccess.NONE, medelegAccess = CsrAccess.NONE, midelegAccess = CsrAccess.NONE)),
      new BranchPlugin(earlyBranch = false, catchAddressMisaligned = true), new FormalPlugin)))
    val ibus = cpu.config.get(classOf[IBusSimplePlugin]).iBus.toAxi4ReadOnly().arValidPipe()
    val dbus = cpu.config.get(classOf[DBusSimplePlugin]).dBus.toAxi4Shared(stageCmd = true)
    val csr = cpu.config.get(classOf[CsrPlugin])
    csr.timerInterrupt := io.interrupts(7)
    csr.softwareInterrupt := io.interrupts(3)
    csr.externalInterrupt := io.interrupts(11)
    val retired = Reg(UInt(32 bits)) init(0)
    when(cpu.config.get(classOf[FormalPlugin]).rvfi.valid) { retired := retired + 1 }
    val arbiter = Axi4SharedArbiter(config, 1, 0, 1, 2)
    arbiter.io.readInputs(0) << ibus
    arbiter.io.sharedInputs(0) << dbus
  }
  io.bus << area.arbiter.io.output.toAxi4()
  io.retired := area.retired
}
