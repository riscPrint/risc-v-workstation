package rvwvexii

import spinal.core._
import spinal.core.sim._
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.{ParamSimple, VexiiRiscv}
import vexiiriscv.misc.{PipelineBuilderPlugin, PrivilegedPlugin, TrapPlugin}

/** RV32IM, machine mode only, cacheless native fetch and LSU buses, no MMU, PMP or debug unit. */
object VexiiTop {
  val configs = Seq("rv32im")

  def param(config: String): ParamSimple = {
    require(configs.contains(config), s"unknown VexiiRiscv config $config")
    val p = new ParamSimple()
    p.xlen = 32
    p.addISA("m")
    p.fixIsaParams()
    p
  }

  def apply(config: String): VexiiRiscv = {
    val plugins = param(config).plugins()
    plugins += new TrapTapPlugin
    ParamSimple.setPma(plugins)
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
