package rvwnax

import spinal.core._
import spinal.core.sim._
import naxriscv.{Config, NaxRiscv}
import naxriscv.compatibility.MultiPortWritesSymplifier
import naxriscv.misc.PrivilegedPlugin
import naxriscv.utilities.Plugin

/** The upstream `naxriscv.Gen` configuration without RVC, FPU or debug: RV32IMA with M/S/U modes,
  * Sv32 MMU, two-wide decode and commit, two ALUs, one shared EU (mul/div/branch/CSR), Lsu2 with
  * 16-entry load and store queues, a 64-entry ROB, BTB, GShare, and 64-byte-line I$ and D$. */
object NaxTop {
  val configs = Seq("rv32imasu")

  def plugins(config: String, probeTap: Boolean = true) = {
    require(configs.contains(config), s"unknown NaxRiscv config $config")
    val l = Config.plugins(
      withRdTime = false,
      aluCount = 2,
      decodeCount = 2,
      withRvc = false,
      withMmu = true,
      withDebug = false,
      withFloat = false,
      withDouble = false,
      withLsu2 = true,
      lqSize = 16,
      sqSize = 16,
      ioRange = a => a(31 downto 28) === 0x1)
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
  }
}
