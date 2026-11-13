package spinalchecks

import spinal.core._

/** Project observations must carry slot and generation, not a reused slot alone.
  * Kill and fence masks come from independent recovery/order intent. Allocation
  * becomes visible after the edge. Release can retire the old generation while
  * allocation reuses its slot. A release denotes completion of all bound effects.
  */
object RecoveryChecks {
  def bind(name: String, slots: Int,
           allocate: Bool, allocateId: UInt, allocateTag: UInt,
           release: Bool, releaseId: UInt, releaseTag: UInt,
           retire: Bool, retireId: UInt, retireTag: UInt,
           deviceEffect: Bool, deviceId: UInt, deviceTag: UInt,
           kill: Bits, fenceStart: Bool, fenceDone: Bool, fenceMask: Bits,
           deviceRequiresRetirement: Boolean = true): Unit = {
    require(slots > 0 && slots <= 32)
    require(Seq(allocate, release, retire, deviceEffect, fenceStart, fenceDone).forall(_ != null), "incomplete recovery event binding")
    val ids = Seq(allocateId, releaseId, retireId, deviceId)
    val tags = Seq(allocateTag, releaseTag, retireTag, deviceTag)
    require(ids.forall(x => x != null && x.getWidth >= Math.max(1, log2Up(slots))), "incomplete recovery slot binding")
    require(tags.forall(_ != null) && tags.map(_.getWidth).distinct.size == 1 && allocateTag.getWidth > 0,
      "recovery events need equal-width generation tags")
    require(kill != null && fenceMask != null && kill.getWidth == slots && fenceMask.getWidth == slots,
      "recovery masks must cover every declared slot")
    require(ClockDomain.current.hasResetSignal || ClockDomain.current.hasSoftResetSignal, "recovery reference state needs reset")
    val owned = Vec.fill(slots)(RegInit(False))
    val killed = Vec.fill(slots)(RegInit(False))
    val retired = Vec.fill(slots)(RegInit(False))
    val generation = Vec.fill(slots)(Reg(UInt(allocateTag.getWidth bits)).init(0))
    def choose(id: UInt, terms: Seq[Bool]): Bool = terms.zipWithIndex.map { case (v,i) => (id === i) && v }.reduce(_ || _)
    def matching(id: UInt, tag: UInt): Seq[Bool] = (0 until slots).map(i => owned(i) && id === i && generation(i) === tag)
    val releasing = matching(releaseId, releaseTag).map(_ && release)
    val live = (0 until slots).map(i => owned(i) && !killed(i) && !kill(i))
    def liveToken(id: UInt, tag: UInt): Bool = choose(id, (0 until slots).map(i => live(i) && generation(i) === tag))
    val retiring = liveToken(retireId, retireTag) && !choose(retireId, retired.toSeq)
    DeclaredChecks.rule("recovery.allocate", name, "allocate a free slot or replace the generation released at this edge")(
      allocate && !choose(allocateId, (0 until slots).map(i => !owned(i) || releasing(i))))
    DeclaredChecks.rule("recovery.release", name, "release the exact owned generation, including canceled work")(
      release && !matching(releaseId, releaseTag).reduce(_ || _))
    DeclaredChecks.rule("recovery.retire", name, "retirement names a live generation once; current kill forbids it")(
      retire && !retiring)
    val committed = choose(deviceId, retired.toSeq) ||
      (retire && retiring && retireId === deviceId && retireTag === deviceTag)
    DeclaredChecks.rule("recovery.device_effect", name, s"accepted device effect names a live generation; retirement required=$deviceRequiresRetirement")(
      deviceEffect && (!liveToken(deviceId, deviceTag) || (if (deviceRequiresRetirement) !committed else False)))
    DeclaredChecks.rule("recovery.kill_retired", name, "the declared speculative kill set excludes committed operations")(
      (0 until slots).map(i => kill(i) && owned(i) && retired(i)).reduce(_ || _))

    val fenceActive = RegInit(False)
    val older = Vec.fill(slots)(RegInit(False))
    val olderTag = Vec.fill(slots)(Reg(UInt(allocateTag.getWidth bits)).init(0))
    val pending = (0 until slots).map(i => owned(i) && !killed(i) && !kill(i) && !releasing(i))
    val waiting = (0 until slots).map(i => pending(i) && Mux(fenceActive,
      older(i) && olderTag(i) === generation(i), fenceMask(i))).reduce(_ || _)
    DeclaredChecks.rule("recovery.fence_lifecycle", name, "one active fence; permit empty and back-to-back completion")(
      (fenceStart && fenceActive && !fenceDone) || (fenceDone && !fenceActive && !fenceStart))
    DeclaredChecks.rule("recovery.fence_drained", name, "selected predecessor generations are released or canceled before completion")(
      fenceDone && waiting)
    when(fenceDone) { fenceActive := False }
    when(fenceStart) {
      fenceActive := !(fenceDone && !fenceActive)
      for(i <- 0 until slots) {
        older(i) := pending(i) && fenceMask(i)
        olderTag(i) := generation(i)
      }
    }
    for(i <- 0 until slots) {
      when((releasing(i) || (kill(i) && owned(i))) && olderTag(i) === generation(i)) { older(i) := False }
      when(retire && retiring && retireId === i) { retired(i) := True }
      when(kill(i) && owned(i)) { killed(i) := True }
      when(releasing(i)) { owned(i) := False; killed(i) := False; retired(i) := False }
      when(allocate && allocateId === i) {
        owned(i) := True; killed(i) := False; retired(i) := False; generation(i) := allocateTag
      }
    }
  }
}
