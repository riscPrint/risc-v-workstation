package rvwvexii

import spinal.core._
import spinal.lib._
import spinal.lib.misc.plugin.FiberPlugin
import spinalprobes.Probe
import vexiiriscv.execute.lsu.{LsuCachelessPlugin, LsuL1Plugin, LsuPlugin}
import vexiiriscv.fetch.{FetchCachelessPlugin, FetchL1Plugin}
import vexiiriscv.memory.MmuPlugin
import vexiiriscv.misc.{PipelineBuilderPlugin, PrivilegedPlugin, TrapPlugin}
import vexiiriscv.test.WhiteboxerPlugin
import vexiiriscv.prediction.{BtbPlugin, LearnPlugin, Prediction}

/** Workstation probes on existing VexiiRiscv signals: the upstream whitebox (commits, learn
  * port, CSR access, load and store events), the cacheless buses, the trap whitebox and, when
  * the config has an MMU, the page-table walker. It changes no core behavior and adds nothing
  * unless the elaboration runs under `Probe.enabled(true)` (C1 `--probes`). */
class ProbeTapPlugin extends FiberPlugin {
  val logic = during setup new Area {
    val pbp = host[PipelineBuilderPlugin]
    val buildBefore = retains(pbp.elaborationLock)
    // Carry the actual final direction. wasWrong also includes target errors.
    val dynamicDirection = Probe.isEnabled && host.get[BtbPlugin].nonEmpty
    if (dynamicDirection) {
      host[LearnPlugin].addLearnCtx(Prediction.ALIGNED_JUMPED)
      host[LearnPlugin].addLearnCtx(Prediction.ALIGNED_JUMPED_PC)
    }
    awaitBuild()
    if (Probe.isEnabled) {
      val wb = host[WhiteboxerPlugin].logic

      // Conditional branches at the learn port. With a BTB, use the carried final prediction.
      // Without a BTB the prediction is sequential, so predicted = taken xor wasWrong.
      val learns = wb.prediction.learns
      for ((l, i) <- learns.zipWithIndex) {
        val p = l.payload
        Probe.branch(s"learn$i", l.valid && p.isBranch, p.pcOnLastSlice, p.taken, p.pcTarget,
          predictedTaken = Some(if (dynamicDirection) p.ctx(Prediction.ALIGNED_JUMPED) else p.taken ^ p.wasWrong),
          predictedTarget = if (dynamicDirection) Some(p.ctx(Prediction.ALIGNED_JUMPED_PC)) else None,
          covers = Seq("cond"))
      }
      val commitId = Reg(UInt(32 bits)) init(0)
      val commitValid = wb.commits.ports.map(_.valid).orR
      when(commitValid) { commitId := commitId + 1 }
      // The named cached config has one commit lane. This is a commit-stage view only.
      require(wb.commits.ports.size == 1, "commit-stage probes require one lane")
      val commitPort = wb.commits.ports.head
      Probe.stage("C", commitPort.valid, commitId, pc = Some(commitPort.pc))
      Probe.retire("commit", commitPort.valid, commitId)
      val recovery = RegInit(False)
      when(commitValid) { recovery := False }
      when(learns.map(l => l.valid && l.payload.wasWrong).orR) { recovery := True }
      Probe.stall("frontend", "mispredict_recovery", recovery && !commitValid, evidence = "inferred")
      host.get[FetchL1Plugin].foreach { f =>
        Probe.stall("fetch", "icache_miss", f.logic.refill.slots.map(_.valid).orR, evidence = "inferred")
      }
      host.get[LsuL1Plugin].foreach { l1 =>
        val bus = l1.logic.bus
        val pending = RegInit(False)
        val beats = Reg(UInt(16 bits)) init(0)
        when(bus.read.cmd.fire) { pending := True; beats := 0 }
        when(bus.read.rsp.fire) {
          beats := beats + 1
          when(beats === bus.p.lineSize * 8 / bus.p.dataWidth - 1) { pending := False }
        }
        Probe.stall("memory", "dcache_miss", pending, evidence = "inferred")
      }
      val retired = wb.commits.ports.map(_.valid.asUInt.resize(4 bits)).reduce(_ + _)
      Probe.counter("cycles", True)
      Probe.counter("retired", retired)
      Probe.counter("branches", learns.map(_.valid).orR)
      Probe.counter("cond_branches", learns.map(l => l.valid && l.payload.isBranch).orR)
      Probe.counter("mispredicts", learns.map(l => l.valid && l.payload.wasWrong).orR, hpm = Some(3))
      Probe.counter("loads", wb.loadExecute.fire, hpm = Some(4))
      Probe.counter("stores", wb.storeCommit.fire, hpm = Some(5))
      Probe.counter("flushes", wb.reschedules.flushes.map(_.valid).orR)

      wb.csr.foreach { c =>
        Probe.csrWrite("csr", c.port.valid && c.port.writeDone, c.port.address, c.port.write)
      }

      val trap = host[TrapPlugin].logic.harts(0).trap
      val cause = (trap.whitebox.interrupt ## trap.whitebox.code.resize(31 bits))
      Probe.interruptTaken("irq", trap.whitebox.trap && trap.whitebox.interrupt, cause, trap.pending.pc)

      host.get[LsuCachelessPlugin].foreach { lsu =>
        val cmd = lsu.logic.bus.cmd
        Probe.bus("dbus", cmd.fire, cmd.address, write = Some(cmd.write), data = Some(cmd.data),
          mask = Some(cmd.mask), size = Some(cmd.size))
      }
      host.get[FetchCachelessPlugin].foreach { f =>
        val cmd = f.logic.bus.cmd
        Probe.bus("ibus", cmd.fire, cmd.address)
      }
      Probe.faultSite("privilege", host[PrivilegedPlugin].logic.harts(0).privilege)

      host.get[FetchL1Plugin].foreach(f => CacheProbes.fetch(f, wb.commits.ports.map(p => (p.valid, p.pc))))
      host.get[LsuL1Plugin].foreach(l1 => CacheProbes.lsu(l1, host[LsuPlugin]))

      // Page-table walks: each PTE response of the refill state machine, then the walk result.
      host.get[MmuPlugin].foreach { mmu =>
        val m = mmu.logic
        val r = m.refill
        val levels = mmu.spec.levels.size
        val inRsp = (0 until levels).map(l => r.isActive(r.RSP(l)))
        val level = OHToUInt(inRsp.asBits()).resize(2 bits)
        Probe.pageWalk("ptw", "response", inRsp.orR && r.load.rsp.valid, r.load.address,
          data = Some(r.load.readed), level = Some(level), fault = Some(r.load.rsp.error(0)))
        val done = mmu.refillPorts.map(p => p.rsp.fire).orR
        val rsp = mmu.refillPorts.head.rsp
        val access = r.permission.execute ? U(2, 2 bits) | (r.permission.write ? U(1, 2 bits) | U(0, 2 bits))
        val status = rsp.pageFault ? U(1, 2 bits) | (rsp.accessFault ? U(2, 2 bits) | U(0, 2 bits))
        val mode = if (mmu.spec.levels.size == 2) "sv32" else s"sv${12 + 9 * levels}"
        Probe.walkResult("ptw", mode, done, r.virtual, access, (m.satp.ppn << 12).resize(34 bits), status, rsp.address)
      }
    }
    buildBefore.release()
  }
}
