package rvwvex

import spinal.core._
import spinal.lib._
import vexriscv.{VexRiscv, VexRiscvConfig}
import vexriscv.plugin._

/** Bare physical-memory RV32IM, with M-only CSRs and no caches, MMU or debug unit. */
object VexTop {
  def configuration(): VexRiscvConfig = VexRiscvConfig(plugins = List(
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
    new MulSimplePlugin,
    new DivPlugin,
    new CsrPlugin(CsrPluginConfig.all2(0x80000000L).copy(userGen = false, supervisorGen = false,
      misaExtensionsInit = 0x1100, misaAccess = CsrAccess.READ_ONLY, ebreakGen = true)),
    new BranchPlugin(earlyBranch = false, catchAddressMisaligned = true),
    new FormalPlugin,
    new TrapProbePlugin))

  def spinalConfig: SpinalConfig = SpinalConfig(defaultConfigForClockDomains =
    ClockDomainConfig(resetKind = spinal.core.SYNC, resetActiveLevel = HIGH))
}

class VexTop extends VexRiscv(VexTop.configuration()) {
  def ibus: IBusSimpleBus = config.get(classOf[IBusSimplePlugin]).iBus
  def dbus: DBusSimpleBus = config.get(classOf[DBusSimplePlugin]).dBus
  def csr: CsrPlugin = config.get(classOf[CsrPlugin])
  def rvfi: RvfiPort = config.get(classOf[FormalPlugin]).rvfi
  def traps: TrapProbePlugin = config.get(classOf[TrapProbePlugin])
}

/** Observe the CSR plugin's trap redirects and actual CSR storage, without changing core sources.
  * With this config a CSR redirect is a trap or XRET. There is no debug redirect.
  * The registered strobe lets the simulator read the values written at trap entry. */
class TrapProbePlugin extends Plugin[VexRiscv] {
  var valid: Bool = null
  var cause, tval: Bits = null

  override def build(pipeline: VexRiscv): Unit = {
    val csr = pipeline.config.get(classOf[CsrPlugin])
    val stage = pipeline.stages.last
    val returning = stage.arbitration.isValid && stage.input(csr.ENV_CTRL) === csr.EnvCtrlEnum.XRET
    valid = out(RegNext(csr.jumpInterface.valid && !returning) init(False)).setName("trap_valid")
    // Read the actual CSR fields for the privilege reached at trap entry.
    def readCsr(address: Int, name: String): Bits = {
      val value = Bits(32 bits).setName(name).allowOverride
      value := 0
      val fields = csr.csrMapping.mapping(address).collect { case r: CsrRead => r }
      require(fields.nonEmpty, s"CSR $address has no readable storage")
      for (r <- fields) value(r.bitOffset, r.that.getBitsWidth bits) := r.that.asBits
      value
    }
    cause = out(Bits(32 bits)).setName("trap_cause")
    tval = out(Bits(32 bits)).setName("trap_tval")
    cause := readCsr(0x342, "trap_mcause")
    tval := readCsr(0x343, "trap_mtval")
  }
}
