package riscvsim

import scala.collection.mutable

/** Project adapters supply physical addresses and accepted events, not raw signal names.
  * Expected bytes are supplied independently before the corresponding cache event. */
final class CacheEventObserver(oracle: MemoryImage, harts: Set[Int], lineBytes: Int,
    sets: Int, ways: Int, eventNames: Map[String, String], replacement: String = "any") {
  private val kinds = Set("fill", "denied", "read", "store", "evict", "invalidate",
    "fetch_request", "fetch_reply", "fetch_consume", "fetch_discard", "publish", "sync")
  require(harts.nonEmpty && eventNames.nonEmpty && eventNames.values.forall(kinds))
  private val caches = harts.map(h => h -> new CacheScoreboard(oracle, lineBytes, sets, ways, replacement)).toMap
  private val visibility = new InstructionVisibility(oracle, harts)
  private case class Fetch(hart: Int, address: Int, publication: String, bytes: Option[Vector[Byte]])
  private val pending = mutable.Map.empty[String, Fetch]
  private val aliases = mutable.Map.empty[(Int, Long), Int]
  private var cycle = -1L
  val coverage = mutable.Map.empty[String, Int].withDefaultValue(0)
  private def bytes(e: ujson.Value): Vector[Byte] = {
    val s = e("bytes").str
    require(s.nonEmpty && s.length % 2 == 0)
    s.grouped(2).map(Integer.parseInt(_, 16).toByte).toVector
  }
  def accept(e: ujson.Value): Unit = {
    val c = e("cycle").num.toLong
    require(c >= cycle && c >= 0); cycle = c
    val kind = eventNames.getOrElse(e("event").str, throw new IllegalArgumentException("undeclared cache event"))
    val hart = e("hart").num.toInt
    require(harts(hart))
    def address = java.lang.Integer.decode(e("physical_address").str).intValue()
    def id = e("id").str
    if (e.obj.contains("virtual_address")) {
      val virtual = java.lang.Long.decode(e("virtual_address").str).longValue()
      if (aliases.exists { case ((h, v), p) => h == hart && v != virtual && p == address }) coverage("alias") += 1
      aliases(hart -> virtual) = address
    }
    kind match {
      case "fill" => caches(hart).fill(address, bytes(e))
      case "denied" => caches(hart).fill(address, bytes(e), denied = true)
      case "read" => caches(hart).read(address, bytes(e))
      case "store" => caches(hart).store(address, bytes(e), BigInt(e("mask").str.stripPrefix("0x"), 16))
      case "evict" => caches(hart).evict(address, e.obj.get("bytes").map(_ => bytes(e)),
        e.obj.get("replacement").exists(_.bool))
      case "invalidate" => caches(hart).invalidate(address)
      case "publish" => visibility.publish(id, address, bytes(e))
      case "sync" => visibility.synchronize(hart, id, e("data_visible").bool, e("fence_i_complete").bool)
      case "fetch_request" =>
        require(!pending.contains(id), "duplicate pending fetch")
        pending(id) = Fetch(hart, address, e("publication").str, None)
      case "fetch_reply" =>
        val f = pending(id)
        require(f.hart == hart && f.bytes.isEmpty, "fetch response identity")
        pending(id) = f.copy(bytes = Some(bytes(e)))
      case "fetch_discard" => require(pending(id).hart == hart); pending.remove(id)
      case "fetch_consume" =>
        val f = pending(id)
        require(f.hart == hart && f.bytes.nonEmpty, "fetch consumed before response")
        visibility.fetch(hart, f.publication, f.address, f.bytes.get)
        pending.remove(id)
    }
    coverage(kind) += 1
  }
  def finish(required: Set[String], instructionChecks: Set[(Int, String)]): Unit = {
    require(required.nonEmpty && required.forall(k => coverage(k) > 0), "missing cache campaign events")
    require(pending.isEmpty, "incomplete fetch requests")
    if (instructionChecks.nonEmpty) visibility.finish(instructionChecks)
  }
}
