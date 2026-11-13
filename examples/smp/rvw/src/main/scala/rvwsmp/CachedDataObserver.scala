package rvwsmp
import riscvsim._

/** One project-selected data line. Expected values come from cached-handoff.S.
  * Flag lines and instruction lines are outside this byte observer's scope. */
class CachedDataObserver {
  val address = BigInt("80080000",16)
  private val oracle = new MemoryImage(64)
  private val writes = scala.collection.mutable.Set.empty[Int]
  private val resident = scala.collection.mutable.Set.empty[Int]
  private val reads = scala.collection.mutable.Set.empty[Int]
  private val events = Set("fill","read","store","writeback","invalidate")
  private val checker = new CacheEventObserver(oracle,Set(0,1),64,1,1,events.map(k=>k->k).toMap)
  def event(kind: String, hart: Int, cycle: Long, data: Seq[Byte] = Nil, mask: BigInt = 0): Unit = {
    val row = ujson.Obj("event"->kind,"hart"->hart,"cycle"->ujson.Num(cycle.toDouble),"physical_address"->"0x0")
    if(data.nonEmpty) row("bytes")=data.map(b=>f"${b&255}%02x").mkString
    if(kind == "store") row("mask")="0x"+mask.toString(16)
    checker.accept(row)
    if(kind == "fill") resident += hart
    if(kind == "invalidate") resident -= hart
  }
  def refill(hart: Int, cycle: Long, bytes: Seq[Byte]): Unit =
    event(if(resident(hart)) "read" else "fill",hart,cycle,bytes)
  def retire(hart: Int, r: RvfiRecord): Unit = if(r.memAddr == address) {
    def bytes(value: BigInt) = (0 until 8).map(i=>((value>>(8*i))&255).toByte)
    if(r.memWmask != 0) {
      require(!writes(hart),"extra data store")
      val expected = if(hart == 0) BigInt(37) else BigInt(85)
      require(r.memWdata == expected && r.memWmask == 255,"unexpected data write")
      oracle.write(0,bytes(expected),255)
      event("store",hart,r.cycle,bytes(r.memWdata),255)
      writes += hart
    }
    if(r.memRmask != 0) {
      require(r.memRdata == (if(hart == 0) BigInt(85) else BigInt(37)),"unexpected data read")
      event("read",hart,r.cycle,bytes(r.memRdata))
      reads += hart
    }
  }
  def finish(): Unit = {
    require(writes == Set(0,1) && reads == Set(0,1),"incomplete two-way data handoff")
    checker.finish(Set("fill","store","read","writeback"),Set.empty)
  }
  def expected: BigInt = oracle.read(0,64).zipWithIndex.foldLeft(BigInt(0)) { case (v,(b,i)) => v | (BigInt(b&255)<<(8*i)) }
  def coverage = ujson.Obj.from(checker.coverage.map { case (k,v) => k->ujson.Num(v) })
}
