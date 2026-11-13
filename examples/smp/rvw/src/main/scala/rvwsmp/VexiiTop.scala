package rvwsmp

import spinal.core._
import spinal.core.sim._
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.{ParamSimple, VexiiRiscv}
import vexiiriscv.misc.{PipelineBuilderPlugin, PrivilegedPlugin, TrapPlugin}

/** RV64IMA, machine mode only, cacheless native fetch and LSU buses, no MMU, PMP or debug unit. */
object VexiiTop {
  val configs = (2 to 8).map(n => s"smp$n")

  def param(config: String): ParamSimple = {
    require(configs.contains(config), s"unknown VexiiRiscv config $config")
    val p = new ParamSimple()
    p.xlen = 64
    p.addISA("m", "a")
    p.fixIsaParams()
    p
  }

  def apply(config: String, hart: Int): VexiiRiscv = {
    val p = param(config)
    p.resetVector = 0x80000000L + hart * 0x20000L
    val plugins = p.plugins(hart)
    plugins += new TrapTapPlugin
    if (sys.env.get("RVW_COSIM_DPI").contains("1")) plugins += new LockstepTapPlugin
    val ioRegion = new spinal.lib.system.tag.PmaRegionImpl(
      mapping = spinal.lib.bus.misc.SizeMapping(0L, 0x80000000L),
      isMain = false, isExecutable = false,
      transfers = spinal.lib.bus.tilelink.M2sTransfers(
        get = spinal.lib.bus.tilelink.SizeRange.all, putFull = spinal.lib.bus.tilelink.SizeRange.all))
    ParamSimple.setPma(plugins, ParamSimple.defaultPma.take(1) :+ ioRegion)
    VexiiRiscv(plugins)
  }

  def spinalConfig: SpinalConfig = SpinalConfig()
}

/** Exposes the values the trap state machine writes to xepc and xtval, and the privilege register.
  * It reads the core's own registers and changes no core behavior. */
class TrapTapPlugin extends FiberPlugin {
  val logic = during setup new Area {
    val pbp = host[PipelineBuilderPlugin]
    val buildBefore = retains(pbp.elaborationLock)
    awaitBuild()
    val trap = host[TrapPlugin].logic.harts(0).trap
    val epc = CombInit(trap.pending.pc).setName("rvw_trap_epc").simPublic()
    val tval = CombInit(trap.fsm.buffer.trap.tval).setName("rvw_trap_tval").simPublic()
    val fire = CombInit(trap.whitebox.trap).setName("rvw_trap_fire").simPublic()
    val privilege = CombInit(host[PrivilegedPlugin].logic.harts(0).privilege).setName("rvw_privilege").simPublic()
    buildBefore.release()
  }
}

/** Project-owned exposure of the generic native transport. */
class LockstepTapPlugin extends FiberPlugin {
  val logic = during setup new Area {
    val buildBefore = retains(host[PipelineBuilderPlugin].elaborationLock)
    awaitBuild()
    val transport = new riscvsim.LockstepDpi
    buildBefore.release()
  }
}

class SmpTop(config: String) extends Component {
  val cores = (0 until config.stripPrefix("smp").toInt).map(h => VexiiTop(config, h))
  val ports = spinal.core.fiber.Fiber patch new Area {
    val fetch = cores.map(_.host[vexiiriscv.fetch.FetchCachelessPlugin].logic.bus.toIo())
    val lsu = cores.map(_.host[vexiiriscv.execute.lsu.LsuCachelessPlugin].logic.bus.toIo())
    val software = cores.map(_.host[PrivilegedPlugin].logic.harts(0).int.m.software.toIo())
    val timer = cores.map(_.host[PrivilegedPlugin].logic.harts(0).int.m.timer.toIo())
    val external = cores.map(_.host[PrivilegedPlugin].logic.harts(0).int.m.external.toIo())
    val time = cores.map(_.host[PrivilegedPlugin].logic.rdtime.toIo())
  }
}
