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
      // ROB indices only address retained state. They are never external event IDs.
      val slots = 1 << c.rob.io.commit.uops(0).rob_idx.getWidth
      val resolved = Vec.fill(slots)(Reg(Bool()) init(False))
      val taken = Vec.fill(slots)(Reg(Bool()) init(False))
      val target = Vec.fill(slots)(Reg(UInt(c.rob.io.commit.uops(0).debug_pc.getWidth bits)))
      for (i <- c.rob.io.enq_valids.indices) {
        when(c.rob.io.enq_valids(i)) { resolved(c.rob.io.enq_uops(i).rob_idx) := False }
      }
      for ((b, i) <- c.brinfos.zipWithIndex) {
        when(b.valid) {
          resolved(b.payload.uop.rob_idx) := True
          taken(b.payload.uop.rob_idx) := b.payload.taken
          target(b.payload.uop.rob_idx) := (b.payload.uop.debug_pc.asSInt + b.payload.target_offset.resize(b.payload.uop.debug_pc.getWidth)).asUInt
        }
        Probe.custom(s"execute_branch_$i", b.valid,
          "pc" -> b.payload.uop.debug_pc, "rob_index" -> b.payload.uop.rob_idx,
          "taken" -> b.payload.taken, "predicted_taken" -> b.payload.uop.taken,
          "mispredict" -> b.payload.mispredict)
      }
      for ((unit, i) <- c.alu_exe_units.zipWithIndex) {
        val r = unit.io_alu_resp
        val u = r.payload.uop
        when(r.valid && u.is_sfb_br) {
          resolved(u.rob_idx) := True
          taken(u.rob_idx) := r.payload.data.lsb
          target(u.rob_idx) := (u.debug_pc.asSInt + boom.util.ImmGen(u.imm_packed, u.imm_sel).asSInt.resize(u.debug_pc.getWidth)).asUInt
        }
      }
      for (i <- c.rob.io.commit.arch_valids.indices) {
        val u = c.rob.io.commit.uops(i)
        val valid = c.rob.io.commit.arch_valids(i) && u.is_br
        val next = Mux(taken(u.rob_idx), target(u.rob_idx),
          u.debug_pc + Mux(u.is_rvc, U(2), U(4)))
        when(valid) { assert(resolved(u.rob_idx), "branch commit lacks resolution") }
        Probe.branch(s"conditional_commit_$i", valid, u.debug_pc, taken(u.rob_idx), next,
          predictedTaken=Some(u.taken), covers=Seq("cond"))
      }
      Probe.custom("mispredict_redirect", c.io.ifu.redirect_val,
        "pc" -> c.io.ifu.redirect_pc, "flush" -> c.rob.io.flush.valid,
        "mispredict" -> c.brupdate.b2.mispredict)
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
    for ((name, rename) <- Seq("integer" -> c.rename_stage, "fp" -> c.fp_rename_stage)) {
      val free = rename.freelist
      free.rework {
        val available = CountOne(free.io.debug_freelist)
        Probe.counter(s"rename_${name}_free", available)
        Probe.counter(s"rename_${name}_allocated", U(free.numPregs, available.getWidth bits) - available)
      }
    }
    c.rob.rework {
      Probe.stall("dispatch", "rob_full", c.rob.full)
      Probe.counter("rob_head_occupancy", CountOne(c.rob.rob_head_vals))
      // Exact slot occupancy from the existing validity registers, not head-tail distance.
      val valid = scala.collection.mutable.ArrayBuffer.empty[Bool]
      c.rob.dslBody.walkStatements {
        case b: Bool if b.isReg && (b.getName().startsWith("rob_val") || b.getScalaLocationLong.contains("rob.scala:335")) => valid += b
        case _ =>
      }
      require(valid.size == (1 << c.rob.rob_head.getWidth), s"ROB validity binding has ${valid.size} entries")
      Probe.counter("rob_occupancy", CountOne(valid))
    }
    val units = Seq("memory" -> c.mem_iss_unit, "alu" -> c.alu_iss_unit,
      "unique" -> c.unq_iss_unit, "fp" -> c.fp_pipeline.issue_unit)
    for ((name, unit) <- units) unit match {
      case q: boom.exu.IssueUnitCollapsing => q.rework {
        Probe.counter(s"issue_${name}_occupancy", CountOne(q.issue_slots.map(_.valid)))
      }
      case _ => // Banked or matrix queues need their own slot mapping.
    }
    val dc = top.tile.dcache
    dc.rework {
      for (i <- dc.s2_valid.indices) {
        Probe.cacheAccess("dcache", s"lookup_$i", dc.s2_valid(i), dc.s2_req(i).addr,
          hit=Some(dc.s2_hit(i)))
        Probe.stall(s"dcache_$i", "nack", dc.s2_valid(i) && dc.s2_nack(i))
      }
    }
    val ls = top.tile.lsu
    ls.rework {
      for (i <- ls.dtlb.io.req.indices) {
        Probe.tlb("dtlb", "miss", ls.dtlb.io.req(i).valid && ls.dtlb.io.resp(i).miss,
          va=Some(ls.dtlb.io.req(i).payload.vaddr))
      }
    }
    val f = top.tile.frontend
    f.rework {
      for (i <- f.f3_bpd_resp.preds.indices) {
        val prediction = f.f3_bpd_resp.preds(i)
        Probe.custom(s"fetch_prediction_$i", f.f3.io.deq.fire && f.f3.io.deq.payload.mask(i),
          "packet_pc" -> f.f3_bpd_resp.pc, "slot" -> U(i, 8 bits),
          "taken" -> prediction.taken, "target_valid" -> prediction.predicted_pc.valid,
          "target" -> prediction.predicted_pc.payload)
      }
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
        Probe.branch(s"commit_$i", r.valid && jump, r.pc_rdata,
          jump || r.pc_wdata =/= r.pc_rdata + 4, r.pc_wdata,
          covers = Seq("jump", "ijump", "call", "icall", "ret"))
        Probe.stage(s"commit_$i", r.valid, r.order, pc = Some(r.pc_rdata))
        Probe.retire(s"commit_$i", r.valid, r.order)
      }
    }
  }
}
