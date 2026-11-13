package rvwvexii

import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.misc.SizeMapping
import spinal.lib.bus.tilelink.{M2sTransfers, SizeRange}
import spinal.lib.system.tag.PmaRegionImpl
import spinal.lib.misc.plugin.FiberPlugin
import vexiiriscv.{ParamSimple, VexiiRiscv}
import vexiiriscv.misc.{PipelineBuilderPlugin, PrivilegedPlugin, TrapPlugin}

/** RV32IM, machine mode only, cacheless native fetch and LSU buses, no MMU, PMP or debug unit.
  * `*_cached` adds the upstream fetch and LSU L1 caches and the BTB/GShare/RAS predictors. */
object VexiiTop {
  val configs = Seq("rv32im", "rv32imasu", "rv64imasu", "rv32im_cached")

  def param(config: String): ParamSimple = {
    require(configs.contains(config), s"unknown VexiiRiscv config $config")
    val p = new ParamSimple()
    p.xlen = if (config.startsWith("rv64")) 64 else 32
    p.addISA("m")
    if (config.endsWith("asu")) {
      p.addISA("a", "s", "u")
      p.asidWidth = if (p.xlen == 64) 16 else 9
      p.pmpParam.pmpSize = 8
      p.pmpParam.granularity = if (p.xlen == 64) 16 else 4
    }
    if (config.endsWith("_cached")) {
      // Upstream L1s (64-byte lines, 2 ways x 32 sets = 4 KiB each; the LSU L1 is write-back)
      // and the upstream predictor stack: BTB, GShare and RAS.
      p.fetchL1Enable = true; p.fetchL1Sets = 32; p.fetchL1Ways = 2
      p.lsuL1Enable = true; p.lsuL1Sets = 32; p.lsuL1Ways = 2
      p.withBtb = true; p.withGShare = true; p.withRas = true
    }
    p.fixIsaParams()
    p
  }

  def apply(config: String, probeTap: Boolean = true): VexiiRiscv = {
    val plugins = param(config).plugins()
    plugins += new TrapTapPlugin
    if (probeTap) plugins += new ProbeTapPlugin
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

  /** Memory initial values inline: the BTB, GShare and RAS RAMs get simulation init content,
    * and RiscvSim's RTL identity needs one generated file. Configs without them are unchanged. */
  def spinalConfig: SpinalConfig = SpinalConfig(inlineRom = true)
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
    val lsu = host[vexiiriscv.execute.lsu.LsuCachelessPlugin].logic
    val lsuVirtualAddress = CombInit(lsu.forkCtrl(lsu.onAddress.RAW_ADDRESS)).setName("rvw_lsu_va").simPublic()
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
