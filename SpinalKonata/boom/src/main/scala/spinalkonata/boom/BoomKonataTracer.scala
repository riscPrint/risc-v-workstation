package spinalkonata.boom

import spinalkonata._

import scala.collection.mutable
import spinal.core.sim._

import _root_.boom.system.KonataProbe

/** Adapted from BOOM at 0cb0b69. The probe tracking algorithm is unchanged;
 * event serialization uses the generic library.
 * Writes a Konata pipeline log (Kanata format 0004, https://github.com/shioyadan/Konata)
 * from a BoomSimTop built with `konataProbe = true`. Call `sample()` once per clock.
 *
 * Instructions are followed from the signals the probe exposes:
 *  - F  : entering / in the fetch buffer
 *  - Dc : in a decode slot, matched in order against the fetch buffer by PC
 *  - Rn : in a rename2 slot, waiting to dispatch
 *  - Iq : in an issue queue (ROB index known from here on)
 *  - Is : issue grant (a speculatively issued uop that gets replayed issues again)
 *  - Ex : register read / execute, until writeback
 *  - Wb : written back to the ROB, waiting to commit
 *  - Cm : commit cycle
 * Mispredicts kill everything younger than the branch, a ROB rollback kills every
 * uncommitted instruction, and a front-end redirect kills everything before dispatch.
 * Killed instructions show as flushed.
 */
class BoomKonataTracer(p: KonataProbe, out: java.io.File, disasm: Map[BigInt, (Long, String)] = Map.empty) {
  private val writer = new KanataWriter(out)

  private final class Uop(val id: Long, val pc: BigInt) { var stage: String = null }

  private var cycle = 0L       // cycle being sampled
  private var nextId = 0L
  /** In-order matching mismatches; non-zero means the trace lost sync somewhere. */
  var desyncs = 0L

  private val fbQ = mutable.Queue[Uop]()
  private val dec = Array.fill[Uop](p.decValid.size)(null)
  private val ren = Array.fill[Uop](p.disValid.size)(null)
  private val rob = mutable.HashMap[Int, Uop]()

  private def emit(at: Long, event: Event): Unit = writer.record(at, event)

  private def create(pc: BigInt, inst: Option[Long], stage: String, at: Long): Uop = {
    val u = new Uop(nextId, pc)
    nextId += 1
    // objdump's text, if it is for the word actually fetched (VM tests run at other addresses)
    val text = disasm.get(pc).filter { case (word, _) => inst.forall(_ == word) }.map(_._2)
      .orElse(inst.map(i => f"$i%08x")).getOrElse("?")
    emit(at, Fetch(u.id, u.id))
    emit(at, Label(u.id, f"$pc%x: $text"))
    inst.foreach(i => emit(at, Label(u.id, f"inst=$i%08x", 1)))
    move(u, stage, at)
    u
  }
  private def move(u: Uop, stage: String, at: Long): Unit = {
    if (u.stage != null) emit(at, Leave(u.id, u.stage))
    emit(at, Enter(u.id, stage))
    u.stage = stage
  }
  private def end(u: Uop, at: Long, flushed: Boolean): Unit = {
    if (u.stage != null) emit(at, Leave(u.id, u.stage))
    emit(at, if (flushed) Flush(u.id) else Retire(u.id))
  }
  private def kill(u: Uop, at: Long): Unit = if (u != null) end(u, at, flushed = true)

  private def killFrontEnd(at: Long): Unit = {
    fbQ.foreach(kill(_, at)); fbQ.clear()
    for (i <- dec.indices) { kill(dec(i), at); dec(i) = null }
    for (i <- ren.indices) { kill(ren(i), at); ren(i) = null }
  }

  /** The fetch-buffer entry that reached decode: the oldest with this PC (older ones were dropped). */
  private def fromFetchBuffer(pc: BigInt, t: Long): Uop = {
    val i = fbQ.indexWhere(_.pc == pc)
    if (i < 0) { desyncs += 1; return create(pc, None, "Dc", t) }
    if (i > 0) desyncs += 1
    for (_ <- 0 until i) kill(fbQ.dequeue(), t)
    val u = fbQ.dequeue()
    move(u, "Dc", t)
    u
  }

  def sample(): Unit = {
    val t = cycle

    // Back end, keyed by ROB index
    for (i <- p.issValid.indices if p.issValid(i).toBoolean)
      rob.get(p.issRobIdx(i).toInt).foreach { u => move(u, "Is", t); move(u, "Ex", t + 1) }
    def writeback(idx: Int): Unit = rob.get(idx).foreach(u => if (u.stage != "Wb") move(u, "Wb", t))
    for (i <- p.wbValid.indices if p.wbValid(i).toBoolean) writeback(p.wbRobIdx(i).toInt)
    for (i <- p.clrValid.indices if p.clrValid(i).toBoolean) writeback(p.clrRobIdx(i).toInt)
    for (i <- p.comValid.indices if p.comValid(i).toBoolean) rob.remove(p.comRobIdx(i).toInt) match {
      case Some(u) => move(u, "Cm", t); end(u, t + 1, flushed = false)
      case None => desyncs += 1
    }
    if (p.mispredict.toBoolean) {
      // Everything younger than the branch (ids are in program order)
      val br = rob.get(p.mispRobIdx.toInt).map(_.id).getOrElse(-1L)
      for ((k, u) <- rob.toSeq if u.id > br) { kill(u, t + 1); rob.remove(k) }
    }
    if (p.rollback.toBoolean) { rob.values.foreach(kill(_, t + 1)); rob.clear() }

    // Rename2 -> dispatch
    for (s <- ren.indices) {
      if (p.disFire(s).toBoolean) {
        val u = if (ren(s) != null) ren(s) else { desyncs += 1; create(p.disPc(s).toBigInt, None, "Rn", t) }
        val idx = p.disRobIdx(s).toInt
        rob.remove(idx).foreach { old => desyncs += 1; kill(old, t) }
        rob(idx) = u
        emit(t + 1, Label(u.id, s"rob=$idx", 1))
        move(u, "Iq", t + 1)
        ren(s) = null
      } else if (!p.disValid(s).toBoolean && ren(s) != null) {
        kill(ren(s), t); ren(s) = null
      }
    }

    // Decode -> rename
    for (s <- dec.indices) {
      if (p.decValid(s).toBoolean) {
        val pc = p.decPc(s).toBigInt
        if (dec(s) == null || dec(s).pc != pc) { kill(dec(s), t); dec(s) = fromFetchBuffer(pc, t) }
        if (p.decFire(s).toBoolean) {
          if (ren(s) != null) { desyncs += 1; kill(ren(s), t) }
          ren(s) = dec(s)
          move(ren(s), "Rn", t + 1)
          dec(s) = null
        }
      } else if (dec(s) != null) {
        kill(dec(s), t); dec(s) = null
      }
    }

    if (p.redirectFlush.toBoolean) killFrontEnd(t + 1)

    // Fetch buffer enqueue (a clear the same cycle drops it)
    if (p.fbClear.toBoolean) { fbQ.foreach(kill(_, t + 1)); fbQ.clear() }
    else if (p.fbDoEnq.toBoolean) for (i <- p.fbMask.indices if p.fbMask(i).toBoolean) {
      val inst = p.fbInst(i).toLong
      val raw = if ((inst & 3) != 3) inst & 0xffff else inst
      fbQ += create(p.fbPc(i).toBigInt, Some(raw), "F", t)
    }

    writer.seal(t)
    cycle += 1
  }

  def close(): Unit = writer.close()
}
