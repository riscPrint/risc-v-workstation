package rvwnax

import spinal.core._
import spinal.core.sim._
import naxriscv.{Config, NaxRiscv}
import naxriscv.compatibility.MultiPortWritesSymplifier
import naxriscv.misc.{PrivilegedPlugin, StaticAddressTranslationPlugin}
import naxriscv.utilities.Plugin

/** The upstream `naxriscv.Gen` configuration without RVC, FPU or debug: RV32IMA with M/S/U modes,
  * Sv32 MMU, two-wide decode and commit, two ALUs, one shared EU (mul/div/branch/CSR), Lsu2 with
  * 16-entry load and store queues, a 64-entry ROB, BTB, GShare, and 64-byte-line I$ and D$. */
object NaxTop {
  val configs = Seq("rv32imasu", "rv32imasu-iq16", "rv32imasu-rob128", "rv32imasu-lq8", "rv32imasu-sq8", "rv64ima", "rv64imasu")

  def xlen(config: String): Int = if (config.startsWith("rv64")) 64 else 32

  def plugins(config: String, probeTap: Boolean = true) = {
    require(configs.contains(config), s"unknown NaxRiscv config $config")
    val l = Config.plugins(
      withRdTime = false,
      aluCount = 2,
      dispatchSlots = if (config == "rv32imasu-iq16") 16 else 32,
      decodeCount = 2,
      robSize = if (config == "rv32imasu-rob128") 128 else 64,
      withRvc = false,
      xlen = xlen(config),
      withMmu = config != "rv64ima",
      withSupervisor = config != "rv64ima",
      withUser = config != "rv64ima",
      withDebug = false,
      withFloat = false,
      withDouble = false,
      withLsu2 = true,
      lqSize = if (config == "rv32imasu-lq8") 8 else 16,
      sqSize = if (config == "rv32imasu-sq8") 8 else 16,
      ioRange = a => a(31 downto 28) === 0x1)
    // With XLEN=64, the static translator requires equal pre/physical widths.
    // Set its public configuration parameter before the core is elaborated.
    if (config == "rv64ima") l.collect { case p: StaticAddressTranslationPlugin => p.physicalWidth = 64 }
    l += new TapPlugin
    if (probeTap) l += new ProbeTapPlugin
    l
  }

  def apply(config: String, probeTap: Boolean = true): NaxRiscv = new NaxRiscv(plugins(config, probeTap))

  def spinalConfig: SpinalConfig = {
    val c = SpinalConfig(inlineRom = true)
    c.addTransformationPhase(new MultiPortWritesSymplifier)
    c
  }
}

/** Exposes the privilege register to simulation. It reads a core register and changes no behavior. */
class TapPlugin extends Plugin {
  val logic = create late new Area {
    val priv = getService[PrivilegedPlugin]
    val privilege = CombInit(priv.setup.get.privilege).setName("rvw_privilege")
    privilege.simPublic()
    // Constant enable for generated counter-bound checks (rvw/micro-checks.json).
    val checksActive = CombInit(True).setName("rvw_checks_active")
    checksActive.simPublic()
  }
}
