package rvwvexii

import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.misc.SizeMapping
import spinal.lib.bus.tilelink.{M2sTransfers, SizeRange}
import spinal.lib.system.tag.PmaRegionImpl
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.{ParamSimple, VexiiRiscv}
import vexiiriscv.misc.{PipelineBuilderPlugin, PrivilegedPlugin, TrapPlugin}

/** RV32IM, machine mode only, cacheless native fetch and LSU buses, no MMU, PMP or debug unit. */
object VexiiTop {
  val configs = Seq("rv32im", "rv32imasu", "rv64imasu")

  def param(config: String): ParamSimple = {
    require(configs.contains(config), s"unknown VexiiRiscv config $config")
    val p = new ParamSimple()
    p.xlen = if (config.startsWith("rv64")) 64 else 32
    p.addISA("m")
    if (config.endsWith("asu")) {
      p.addISA("a", "s", "u")
      p.pmpParam.pmpSize = 8
      p.pmpParam.granularity = if (p.xlen == 64) 16 else 4
    }
    p.fixIsaParams()
    p
  }

  def apply(config: String): VexiiRiscv = {
    val plugins = param(config).plugins()
    plugins += new TrapTapPlugin
    if (sys.env.get("RVW_COSIM_DPI").contains("1")) plugins += new LockstepTapPlugin
    val deviceRegions = sys.env.get("RVW_VEX_DEVICE_MAP").toSeq.flatMap { path =>
      ujson.read(java.nio.file.Files.readString(java.nio.file.Path.of(path)))("devices").arr.map { row =>
        new PmaRegionImpl(
          mapping = SizeMapping(java.lang.Long.decode(row("base").str).longValue(), java.lang.Long.decode(row("size").str).longValue()),
          isMain = false, isExecutable = false,
          transfers = M2sTransfers(get = SizeRange.all, putFull = SizeRange.all))
      }
    }
    ParamSimple.setPma(plugins, ParamSimple.defaultPma ++ deviceRegions)
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
