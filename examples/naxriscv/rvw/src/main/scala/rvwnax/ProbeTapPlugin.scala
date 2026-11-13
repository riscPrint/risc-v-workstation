package rvwnax

import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinalprobes.Probe
import naxriscv.Global
import naxriscv.fetch.FetchCachePlugin
import naxriscv.{Frontend, ROB}
import naxriscv.frontend.{DispatchPlugin, FrontendPlugin, RfAllocationPlugin}
import naxriscv.lsu.DataCachePlugin
import naxriscv.lsu2.Lsu2Plugin
import naxriscv.misc.{CommitPlugin, RobPlugin, MmuPlugin, PrivilegedPlugin}
import naxriscv.prediction.{BranchContextPlugin, Prediction}
import naxriscv.utilities.Plugin

/** Workstation probes on existing NaxRiscv signals. It reads core signals only (the commit,
  * reschedule and ROB pointers, the register allocator, the issue queue, the load/store queue
  * trackers, the refill buses and the branch learn port) and adds nothing unless the elaboration
  * runs under `Probe.enabled(true)` (C1 `--probes`).
  *
  * Top-down counters partition the commit slots of each cycle, with the same predicates as the
  * workstation OoO model (`rvw/src/rvw/ooo/attribution.py`): retired slots are `retiring`; the
  * other slots are `bad_speculation` while a recovery is in flight (from an execute-time or
  * commit-time reschedule until the next ROB allocation), else `backend_bound` when the ROB holds
  * work, else `frontend_bound`. */
class ProbeTapPlugin extends Plugin {
  val setup = create early new Area {
    val bcp = getService[BranchContextPlugin]
    bcp.retain()
    // Hold the front-end pipeline until the stage probes have read their stageables.
    val frontend = getService[FrontendPlugin]
    frontend.retain()
  }

  val logic = create late new Area {
    val c2Instructions = scala.collection.mutable.ArrayBuffer.empty[Bits]
    var c2VirtualAddress = Option.empty[UInt]
    var c2TrapEpc = Option.empty[UInt]
    var c2TrapTvalWrite = Option.empty[Bool]
    var c2TrapTval = Option.empty[Bits]
    var mmuWalk = Option.empty[MmuWalkTap]
    val bcp = getService[BranchContextPlugin]
    // The learn values must be requested while this plugin holds the branch-context lock. Release
    // it before waiting on any other plugin, so the branch context builds with the pipeline.
    val learnKeys = if (Probe.isEnabled) Some((bcp.learnRead(bcp.keys.BRANCH_FINAL), bcp.learnRead(Prediction.IS_BRANCH))) else None
    bcp.release()
    if (!Probe.isEnabled) setup.get.frontend.release()
    if (Probe.isEnabled) {
      val commit = getService[CommitPlugin].logic.get
      val wb = commit.whitebox
      val width = Global.COMMIT_COUNT.get
      val mask = wb.commit.mask
      val retired = CountOne(mask)

      // Recovery: an execute-time reschedule (a mispredicted branch, a trap) waits for commit;
      // the commit-time reschedule flushes; the front end refills until the next ROB allocation.
      val early = commit.reschedule.reschedulePort.valid
      val flush = wb.reschedule.valid
      val alloc = wb.robToPc.valid
      val pending = RegInit(False)
      val refill = RegInit(False)
      when(early) { pending := True }
      when(alloc) { refill := False }
      when(flush) { pending := False; refill := True }
      val recovering = pending || refill || early || flush
      val robWork = !commit.ptr.empty
      val lost = U(width, log2Up(width + 1) bits) - retired
      Probe.custom("topdown_cycle", True,
        "retiring" -> retired,
        "bad_speculation" -> (recovering ? lost | U(0)),
        "backend_bound" -> ((!recovering && robWork) ? lost | U(0)),
        "frontend_bound" -> ((!recovering && !robWork) ? lost | U(0)))
      Probe.counter("topdown_slots", U(width, log2Up(width + 1) bits))
      Probe.counter("topdown_retiring", retired)
      Probe.counter("topdown_bad_speculation", recovering ? lost | U(0))
      Probe.counter("topdown_backend_bound", (!recovering && robWork) ? lost | U(0))
      Probe.counter("topdown_frontend_bound", (!recovering && !robWork) ? lost | U(0))

      Probe.counter("cycles", True)
      Probe.counter("retired", retired)
      Probe.counter("rob_alloc_lines", alloc)
      Probe.counter("rob_occupancy", (commit.ptr.alloc - commit.ptr.commit).resize(8 bits))
      Probe.counter("reschedule_execute", early)
      Probe.counter("reschedule_commit", flush)
      Probe.counter("reschedule_commit_trap", flush && wb.reschedule.trap)

      // Integer physical register free list: allocations at dispatch, returns at commit or flush.
      val rf = getServicesOf[RfAllocationPlugin].head.logic.get.allocator.io
      Probe.counter("freelist_alloc", rf.pop.fire ? CountOne(rf.pop.mask) | U(0))
      Probe.counter("freelist_free", CountOne(rf.push.map(_.valid).asBits()))

      val iq = getService[DispatchPlugin].logic.get.queue.io
      Probe.counter("iq_occupancy", CountOne(iq.usage))
      Probe.counter("iq_full_cycles", iq.usage.andR)
      Probe.counter("iq_push_blocked", getService[DispatchPlugin].logic.get.push.stage.isValid && !iq.push.ready)

      val lsu = getService[Lsu2Plugin]
      // Read the explicit LSU control result, not cache latency or aggregate reschedules.
      val control = lsu.logic.get.sharedPip.ctrl.stage
      val retry = control.isFireing
      Probe.stageAt("lsu_attempt", "Ls", retry, control(ROB.ID))
      val status = control(lsu.keys.CTRL)
      Probe.lsuRetry("translation", retry && status === Lsu2Plugin.CTRL_ENUM.MMU_REDO,
        control(ROB.ID), "tlb_miss")
      Probe.lsuRetry("forward", retry && status === Lsu2Plugin.CTRL_ENUM.LOAD_HAZARD,
        control(ROB.ID), "store_forward_miss")
      Probe.lsuRetry("cache", retry && status === Lsu2Plugin.CTRL_ENUM.LOAD_MISS,
        control(ROB.ID), "cache_miss_retry")
      Probe.lsuRetry("order", retry && !control(lsu.keys.TRAP_SPECULATION) && status === Lsu2Plugin.CTRL_ENUM.SUCCESS &&
        !control(lsu.keys.IS_LOAD) && control(lsu.keys.YOUNGER_LOAD_RESCHEDULE),
        control(lsu.keys.YOUNGER_LOAD_ROB), "memory_order_violation")
      val lq = lsu.logic.get.lq.tracker
      val sq = lsu.logic.get.sq.tracker
      Probe.counter("lq_occupancy", U(lsu.lqSize, 8 bits) - lq.free.resize(8 bits))
      Probe.counter("sq_occupancy", U(lsu.sqSize, 8 bits) - sq.free.resize(8 bits))
      Probe.counter("lq_full_cycles", lq.free === 0)
      Probe.counter("sq_full_cycles", sq.free === 0)

      val ibus = getService[FetchCachePlugin].mem.get
      val dmem = getService[DataCachePlugin].mem.get
      Probe.counter("icache_refills", ibus.cmd.fire)
      Probe.counter("dcache_refills", dmem.read.cmd.fire)
      Probe.counter("dcache_writebacks", dmem.write.cmd.fire && dmem.write.cmd.last)

      // Pipeline view (Kanata): one instruction per ROB entry, from ROB allocation (rename,
      // the first stage) through dispatch, issue, operand read/execute, completion and commit.
      // A commit-time reschedule flushes every younger entry, and the entry itself on a trap.
      val privileged = getService[PrivilegedPlugin]
      c2TrapTvalWrite = Some(CombInit(privileged.logic.get.fsm.isActive(privileged.logic.get.fsm.TVAL_WRITE) &&
        privileged.setup.get.ramWrite.valid && privileged.setup.get.ramWrite.ready)
        .setName("rvw_c2_trap_tval_write").simPublic())
      c2TrapTval = Some(CombInit(privileged.setup.get.ramWrite.data)
        .setName("rvw_c2_trap_tval").simPublic())
      c2TrapEpc = Some(CombInit(privileged.logic.get.reschedule.epc)
        .setName("rvw_c2_trap_epc").simPublic())
      val cols = ROB.COLS
      val allocated = setup.get.frontend.pipeline.allocated
      for (i <- 0 until cols) c2Instructions += CombInit(allocated(Frontend.MICRO_OP, i))
        .setName(s"rvw_c2_instruction_$i").simPublic()
      c2VirtualAddress = Some(CombInit(lsu.logic.get.sharedPip.cacheRsp.stage(lsu.keys.ADDRESS_PRE_TRANSLATION))
        .setName("rvw_c2_virtual_address").simPublic())
      val dispatch = getService[DispatchPlugin].logic.get.push.stage
      for (i <- 0 until cols) {
        Probe.stageAt(s"rename_$i", "Rn", allocated.isFireing && allocated(Frontend.DISPATCH_MASK, i),
          (allocated(ROB.ID) + i).resize(ROB.ID_WIDTH bits), Some(wb.robToPc.pc(i).asUInt), first = true)
        Probe.stageAt(s"dispatch_$i", "Ds", dispatch.isFireing && dispatch(Frontend.DISPATCH_MASK, i),
          (dispatch(ROB.ID) + i).resize(ROB.ID_WIDTH bits))
        Probe.retire(s"commit_$i", mask(i), (wb.commit.robId + i).resize(ROB.ID_WIDTH bits))
      }
      setup.get.frontend.release()
      for ((port, i) <- getService[DispatchPlugin].logic.get.whitebox.issuePorts.zipWithIndex) {
        Probe.stageAt(s"issue_$i", "Is", port.valid, port.payload.robId)
        Probe.stageAt(s"execute_$i", "Ex", RegNext(port.valid) init(False), RegNext(port.payload.robId))
      }
      for ((port, i) <- getService[RobPlugin].logic.get.whitebox.completionsPorts.zipWithIndex)
        Probe.stageAt(s"complete_$i", "Wb", port.valid, port.payload.id)
      Probe.flushYounger("reschedule", wb.reschedule.valid, wb.reschedule.robId, wb.reschedule.skipCommit)
      mmuWalk = getServicesOf[MmuPlugin].headOption.map(new MmuWalkTap(_))

    }
  }

  /** Conditional branches at the learn port: one event per committed branch, in commit order.
    * The prediction is the dispatch-time context (BRANCH_EARLY) of the same branch. */
  val branches = create late new Area {
    val bcp = getService[BranchContextPlugin]
    logic.get.learnKeys.foreach { case (ctx, isBranch) =>
      val free = bcp.free.get
      val predicted = bcp.logic.get.mem.earlyBranch.readAsync(free.learn.bid)
      val learn = bcp.learnValid && isBranch
      Probe.branch("learn", learn, ctx.pcOnLastSlice, ctx.taken, ctx.pcTarget,
        predictedTaken = Some(predicted.taken), predictedTarget = Some(predicted.pc),
        semantics = "first-prediction", covers = Seq("cond"))
      Probe.counter("branches", bcp.learnValid)
      Probe.counter("cond_branches", learn)
      Probe.counter("cond_mispredicts", learn && predicted.taken =/= ctx.taken)
      Probe.counter("cond_taken", learn && ctx.taken)
    }
  }
}


/** Samples the MMU's own cache-load port. A redo is a retry, not a returned PTE. */
class MmuWalkTap(mmu: MmuPlugin) extends Area {
  val command = CombInit(mmu.setup.get.cacheLoad.cmd.fire).setName("rvw_ptw_command").simPublic()
  val address = CombInit(mmu.setup.get.cacheLoad.cmd.virtual).setName("rvw_ptw_address").simPublic()
  val response = CombInit(mmu.logic.get.refill.load.rsp.valid).setName("rvw_ptw_response").simPublic()
  val retry = CombInit(mmu.logic.get.refill.load.rsp.redo).setName("rvw_ptw_retry").simPublic()
  val fault = CombInit(mmu.logic.get.refill.load.rsp.fault).setName("rvw_ptw_fault").simPublic()
  val data = CombInit(mmu.logic.get.refill.load.readed).setName("rvw_ptw_data").simPublic()
}
