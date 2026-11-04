package spinalchecks

import spinal.core._

/** Explicit token lifetime and operand readiness. Tokens must include a generation if IDs can be reused. */
object ExecutionChecks {
  def bind(name: String, slots: Int, operands: Int,
           allocate: Bool, allocateId: UInt, initialReady: Bits,
           wake: Bool, wakeId: UInt, wakeMask: Bits,
           issue: Bool, issueId: UInt,
           replay: Bool, replayId: UInt,
           writeback: Bool, writebackId: UInt, cancel: Bits): Unit = {
    require(slots > 0 && slots <= 32 && operands > 0)
    require(Seq(allocate, wake, issue, replay, writeback).forall(_ != null), "incomplete execution binding")
    require(Seq(allocateId, wakeId, issueId, replayId, writebackId).forall(x => x != null && x.getWidth >= Math.max(1, log2Up(slots))),
      "incomplete execution token binding")
    require(initialReady != null && wakeMask != null && cancel != null, "incomplete execution binding")
    require(initialReady.getWidth == operands && wakeMask.getWidth == operands && cancel.getWidth == slots)
    require(ClockDomain.current.hasResetSignal || ClockDomain.current.hasSoftResetSignal,
      "execution reference state needs a reset domain")
    val live = Vec.fill(slots)(Reg(Bool()).init(False))
    val issued = Vec.fill(slots)(Reg(Bool()).init(False))
    val ready = Vec.fill(slots)(Reg(Bits(operands bits)).init(0))
    def choose(id: UInt, terms: Seq[Bool]): Bool = terms.zipWithIndex.map { case (v,i) => (id === i) && v }.reduce(_ || _)
    val allocFree = choose(allocateId, live.map(!_).toSeq)
    val wakeLive = choose(wakeId, live.toSeq)
    val issueLive = choose(issueId, (0 until slots).map(i => live(i) && !issued(i)))
    val issueReady = choose(issueId, ready.map(_.andR).toSeq)
    val replayLive = choose(replayId, (0 until slots).map(i => live(i) && issued(i)))
    val wbLive = choose(writebackId, (0 until slots).map(i => live(i) && issued(i) && !cancel(i)))
    DeclaredChecks.rule("execution.allocate", name, "allocate a free in-range token; no same-cycle reuse")(
      allocate && !allocFree)
    DeclaredChecks.rule("execution.wakeup", name, "wakeup names a live token before this edge")(
      wake && !wakeLive)
    DeclaredChecks.rule("execution.issue", name, "issue names a live unissued token; cancellation forbids issue")(
      issue && (!issueLive || choose(issueId, cancel.asBools.toSeq)))
    DeclaredChecks.rule("execution.operands", name, "all declared operands ready before issue; no same-cycle wake bypass")(
      issue && issueLive && !issueReady)
    DeclaredChecks.rule("execution.replay", name, "replay names a live issued token")(
      replay && !replayLive)
    DeclaredChecks.rule("execution.writeback", name, "writeback names a live issued token; cancellation forbids writeback")(
      writeback && !wbLive)
    for (i <- 0 until slots) {
      // State priority: cancellation, completion, replay, issue, allocation. Wakeup only changes readiness.
      when(wake && wakeId === i && live(i)) { ready(i) := ready(i) | wakeMask }
      when(allocate && allocateId === i && !live(i)) {
        live(i) := True; issued(i) := False; ready(i) := initialReady
      }
      when(issue && issueId === i && live(i)) { issued(i) := True }
      when(replay && replayId === i && live(i)) { issued(i) := False }
      when(writeback && writebackId === i && live(i)) { live(i) := False; issued(i) := False }
      when(cancel(i)) { live(i) := False; issued(i) := False; ready(i) := 0 }
    }
  }
}
