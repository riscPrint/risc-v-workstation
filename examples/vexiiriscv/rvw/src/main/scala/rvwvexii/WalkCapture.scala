package rvwvexii

import scala.collection.mutable

/** Builds C2 `mmu_walk` records (docs/contracts/mmu.md) from the sampled `WalkTap` signals.
  * Every field comes from the walker: start request, PTE reads on its bus port and the refill
  * response. Nothing is taken from retirement results or from the reference model.
  * Within one sampled cycle, call `start`, `response`, `command`, then `done`. */
class WalkCapture(xlen: Int, vaWidth: Int) {
  require(xlen == 32 || xlen == 64, "unsupported XLEN")
  val mode: String = if (xlen == 64) "sv39" else "sv32"
  private val levels = if (xlen == 64) 3 else 2
  private val xmask = (BigInt(1) << xlen) - 1
  private case class Active(va: BigInt, access: String, root: BigInt, reads: mutable.ArrayBuffer[ujson.Obj],
                            var command: Option[BigInt])
  private var active = Option.empty[Active]
  private val completed = mutable.Queue.empty[(Long, ujson.Obj)]
  private var nextId = 0

  private def hex(v: BigInt): String = "0x" + v.toString(16)
  private def signExtend(v: BigInt): BigInt = {
    val raw = v & ((BigInt(1) << vaWidth) - 1)
    (if (vaWidth < xlen && raw.testBit(vaWidth - 1)) raw - (BigInt(1) << vaWidth) else raw) & xmask
  }

  def start(va: BigInt, read: Boolean, write: Boolean, execute: Boolean, rootPpn: BigInt): Unit = {
    require(active.isEmpty, "walk started while another walk is active")
    val access = if (execute) "fetch" else if (write) "store" else if (read) "load" else
      throw new IllegalStateException("walk request has no permission")
    active = Some(Active(signExtend(va), access, rootPpn << 12, mutable.ArrayBuffer.empty, None))
  }

  def command(address: BigInt): Unit = {
    val a = active.getOrElse(throw new IllegalStateException("PTE read outside a walk"))
    require(a.command.isEmpty, "PTE read issued before the previous response")
    require(a.reads.size < levels, "walk reads more PTEs than the mode has levels")
    a.command = Some(address)
  }

  def response(data: BigInt, error: Boolean): Unit = {
    val a = active.getOrElse(throw new IllegalStateException("PTE response outside a walk"))
    val address = a.command.getOrElse(throw new IllegalStateException("PTE response without a read"))
    val read = ujson.Obj("level" -> (levels - 1 - a.reads.size), "address" -> hex(address), "fault" -> error)
    if (!error) read("data") = hex(data & xmask)
    a.reads += read
    a.command = None
  }

  def done(cycle: Long, pageFault: Boolean, accessFault: Boolean, address: BigInt): Unit = {
    val a = active.getOrElse(throw new IllegalStateException("walk response without a walk"))
    require(a.command.isEmpty, "walk ended with a PTE read outstanding")
    val status = if (pageFault) "page-fault" else if (accessFault) "access-fault" else "success"
    val record = ujson.Obj("kind" -> "mmu_walk", "access_id" -> nextId, "mode" -> mode, "access" -> a.access,
      "va" -> hex(a.va), "root" -> hex(a.root), "status" -> status, "reads" -> ujson.Arr.from(a.reads))
    if (status == "success") record("pa") = hex(address)
    completed.enqueue((cycle, record))
    nextId += 1
    active = None
  }

  /** Records whose walk ended at or before `cycle`, removed in walk order. */
  def due(cycle: Long): Seq[ujson.Obj] = completed.dequeueWhile(_._1 <= cycle).map(_._2).toSeq

  def walks: Int = nextId
  def undelivered: Int = completed.size + active.size
}
