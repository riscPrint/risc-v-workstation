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
  def liveMap = riscvsim.SimMap.load(sys.props.get("rvwvexii.bootMap").map(new java.io.File(_)).getOrElse(new java.io.File(new java.io.File(sys.props("riscvsim.script")).getParentFile, "live-devices.json")))
  val configs = Seq("rv32im", "rv32imasu", "rv64imasu", "rv64ima", "rv64imacsu", "rv64imacsu_linux", "rv32im_cached", "rv32im_bitpasta", "rv32im_bitpasta_ipc")

  def supervisor(config: String) = config.endsWith("asu") || config.startsWith("rv64imacsu")
  def compressed(config: String) = config.startsWith("rv64imacsu")
  def param(config: String): ParamSimple = {
    require(configs.contains(config), s"unknown VexiiRiscv config $config")
    val p = new ParamSimple()
    p.xlen = if (config.startsWith("rv64")) 64 else 32
    p.addISA("m")
    if (config.startsWith("rv32im_bitpasta")) {
      p.divImpl = "bitpasta"
      p.divArea = !config.endsWith("_ipc")
    }
    if (config == "rv64ima") p.addISA("a")
    if (supervisor(config)) {
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
    if (compressed(config)) p.addISA("c")
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
    val liveRegions = Seq(liveMap).flatMap { map =>
      map.regions.filter(_.kind == "mmio").map { r =>
        new PmaRegionImpl(mapping = SizeMapping(r.base.toLong, r.size.toLong),
          isMain = false, isExecutable = false,
          transfers = M2sTransfers(get = SizeRange.all, putFull = SizeRange.all))
      }
    }
    ParamSimple.setPma(plugins, ParamSimple.defaultPma ++ deviceRegions ++ liveRegions)
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
    val epc = CombInit(vexiiriscv.Global.expendPc(trap.pending.pc, vexiiriscv.riscv.Riscv.XLEN.get)).setName("rvw_trap_epc").simPublic()
    // The CSR write path widens the buffered tval with expendPc (sign extension above TVAL_WIDTH).
    val tval = CombInit(vexiiriscv.Global.expendPc(trap.fsm.buffer.trap.tval.asUInt, vexiiriscv.riscv.Riscv.XLEN.get))
      .setName("rvw_trap_tval").simPublic()
    val cause = CombInit(trap.whitebox.interrupt ## trap.whitebox.code.resize(vexiiriscv.riscv.Riscv.XLEN.get - 1)).setName("rvw_trap_cause").simPublic()
    val fire = CombInit(trap.whitebox.trap).setName("rvw_trap_fire").simPublic()
    // Cacheless LSU only: the address that its bus command carries before translation.
    val lsuVirtualAddress = host.get[vexiiriscv.execute.lsu.LsuCachelessPlugin].map(_.logic).map(lsu =>
      CombInit(lsu.forkCtrl(lsu.onAddress.RAW_ADDRESS)).setName("rvw_lsu_va").simPublic())
    val privilege = CombInit(host[PrivilegedPlugin].logic.harts(0).privilege).setName("rvw_privilege").simPublic()
    val walk = host.get[vexiiriscv.memory.MmuPlugin].map(new WalkTap(_))
    buildBefore.release()
  }
}

/** Page-table walks of the MMU refill state machine: start (VA, requested permission, satp root),
  * each PTE read on the walker's bus port, and the refill response (fault flags, physical address).
  * The response already includes the walker's permission check. Only reads; no core behavior changes. */
class WalkTap(mmu: vexiiriscv.memory.MmuPlugin) extends Area {
  // No member holds `mmu.logic` itself: its inferred structural type breaks incremental compilation.
  val start = CombInit(!mmu.logic.refill.busy && mmu.logic.refill.arbiter.io.output.valid).setName("rvw_walk_start").simPublic()
  val va = CombInit(mmu.logic.refill.arbiter.io.output.address).setName("rvw_walk_va").simPublic()
  val read = CombInit(mmu.logic.refill.arbiter.io.output.permission.read).setName("rvw_walk_read").simPublic()
  val write = CombInit(mmu.logic.refill.arbiter.io.output.permission.write).setName("rvw_walk_write").simPublic()
  val execute = CombInit(mmu.logic.refill.arbiter.io.output.permission.execute).setName("rvw_walk_execute").simPublic()
  val rootPpn = CombInit(mmu.logic.satp.ppn).setName("rvw_walk_root_ppn").simPublic()
  val pteCmd = CombInit(mmu.logic.accessBus.cmd.fire).setName("rvw_walk_pte_cmd").simPublic()
  val pteAddress = CombInit(mmu.logic.accessBus.cmd.address).setName("rvw_walk_pte_address").simPublic()
  val pteRsp = CombInit(mmu.logic.accessBus.rsp.valid).setName("rvw_walk_pte_rsp").simPublic()
  val pteData = CombInit(mmu.logic.accessBus.rsp.data).setName("rvw_walk_pte_data").simPublic()
  val pteError = CombInit(mmu.logic.accessBus.rsp.error.orR).setName("rvw_walk_pte_error").simPublic()
  val done = CombInit(mmu.refillPorts.map(p => p.rsp.valid && p.rsp.ready).reduce(_ || _)).setName("rvw_walk_done").simPublic()
  val pageFault = CombInit(mmu.refillPorts.head.rsp.pageFault).setName("rvw_walk_page_fault").simPublic()
  val accessFault = CombInit(mmu.refillPorts.head.rsp.accessFault).setName("rvw_walk_access_fault").simPublic()
  val address = CombInit(mmu.refillPorts.head.rsp.address).setName("rvw_walk_address").simPublic()
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
