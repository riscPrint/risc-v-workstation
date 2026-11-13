package riscvsim.boom

import spinal.core._
import spinal.lib.CountOne
import spinalprobes.Probe
import boom.system.BoomSimTop

/** Simulation-only taps. No changes to the core sources are required. */
object BoomProbes {
  def bind(top: BoomSimTop): Unit = {
    val c = top.tile.core
    // Bind in each signal owner's scope to preserve Spinal hierarchy rules.
    c.rework {
      Probe.counter("commits", CountOne(c.rob.io.commit.valids))
      Probe.counter("architectural_commits", CountOne(c.rob.io.commit.arch_valids))
      Probe.counter("predicated_off_commits", CountOne(c.rob.io.commit.valids.asBits & ~c.rob.io.commit.arch_valids.asBits))
      Probe.counter("branch_mispredict", c.brupdate.b2.mispredict)
      Probe.custom("branch_resolution", c.brupdate.b2.mispredict,
        "rob_index" -> c.brupdate.b2.uop.rob_idx, "taken" -> c.brupdate.b2.taken)
      for (i <- c.ren_stalls.indices) {
        Probe.stall(s"rename_$i", "rename_unavailable", c.ren_stalls(i))
        Probe.stall(s"dispatch_$i", "dispatch_blocked", c.dis_valids(i) && c.dis_stalls(i))
      }
      Probe.counter("rename_occupancy", CountOne(c.dis_valids))
    }
    c.rob.rework {
      Probe.stall("dispatch", "rob_full", c.rob.full)
      Probe.counter("rob_head_occupancy", CountOne(c.rob.rob_head_vals))
      // Exact slot occupancy from the existing validity registers, not head-tail distance.
      val valid = scala.collection.mutable.ArrayBuffer.empty[Bool]
      c.rob.dslBody.walkStatements {
        case b: Bool if b.isReg && b.getName().startsWith("rob_val") => valid += b
        case _ =>
      }
      if (valid.nonEmpty) Probe.counter("rob_occupancy", CountOne(valid))
    }
    val units = Seq("memory" -> c.mem_iss_unit, "alu" -> c.alu_iss_unit,
      "unique" -> c.unq_iss_unit, "fp" -> c.fp_pipeline.issue_unit)
    for ((name, unit) <- units) unit match {
      case q: boom.exu.IssueUnitCollapsing => q.rework {
        Probe.counter(s"issue_${name}_occupancy", CountOne(q.issue_slots.map(_.valid)))
      }
      case _ => // Banked or matrix queues need their own slot mapping.
    }
    val f = top.tile.frontend
    f.rework {
      Probe.tlb("itlb", "miss", f.tlb.io.req.valid && f.s1_tlb_miss, va = Some(f.tlb.io.req.payload.vaddr))
      Probe.cacheAccess("icache", "response", f.icache.io.resp.valid, f.s2_ppc,
        data = Some(f.icache.io.resp.payload.data))
      Probe.counter("icache_responses", f.icache.io.resp.valid)
    }
    val ptw = top.tile.ptw
    ptw.rework {
      Probe.pageWalk("ptw", "request", ptw.io.mem.req.fire, ptw.io.mem.req.payload.addr)
      Probe.pageWalk("ptw", "response", ptw.io.mem.resp.valid, ptw.io.mem.resp.payload.addr,
        data = Some(ptw.io.mem.resp.payload.data))
    }
    top.rework {
      if (top.io.rvfi != null) for ((r, i) <- top.io.rvfi.zipWithIndex) {
        val branch = r.insn(6 downto 0) === U(0x63, 7 bits)
        val jump = r.insn(6 downto 0) === U(0x6f, 7 bits) || r.insn(6 downto 0) === U(0x67, 7 bits)
        Probe.branch(s"commit_$i", r.valid && (branch || jump), r.pc_rdata,
          jump || r.pc_wdata =/= r.pc_rdata + 4, r.pc_wdata,
          covers = Seq("cond", "jump", "ijump", "call", "icall", "ret"))
        Probe.stage(s"commit_$i", r.valid, r.order, pc = Some(r.pc_rdata))
        Probe.retire(s"commit_$i", r.valid, r.order)
      }
    }
  }
}
