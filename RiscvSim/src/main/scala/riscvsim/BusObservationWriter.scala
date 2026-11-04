package riscvsim

import java.io.{File, PrintWriter}

/** Passive accepted-channel capture. No retirement inputs and no correctness verdict. */
final class BusObservationWriter(file: File, identity: ujson.Obj, val busBytes: Int) extends AutoCloseable {
  require(busBytes > 0 && (busBytes & (busBytes - 1)) == 0)
  private val out = new PrintWriter(file)
  private var lastCycle = -1L
  private var sequence = 0L
  out.println(ujson.write(ujson.Obj("schema" -> "rvw.bus-observations/1", "identity" -> identity,
    "bus_bytes" -> busBytes, "boundary" -> "accepted-external-tilelink", "independent" -> true)))
  def sample(channel: String, cycle: Long, fields: (String, ujson.Value)*): Unit = {
    require(Set("a", "d")(channel), "unsupported bus channel")
    require(cycle >= 0 && cycle >= lastCycle, "bus observation cycle order")
    require(!fields.exists(p => Set("channel", "cycle", "sequence", "kind")(p._1)), "reserved bus field")
    lastCycle = cycle
    val row = ujson.Obj("channel" -> channel, "cycle" -> ujson.Str(cycle.toString), "sequence" -> ujson.Str(sequence.toString))
    fields.foreach { case (k,v) => row(k) = v }
    out.println(ujson.write(row)); sequence += 1
  }
  def end(cycle: Long, status: String): Unit = {
    require(cycle >= lastCycle)
    out.println(ujson.write(ujson.Obj("kind" -> "end", "cycle" -> ujson.Str(cycle.toString), "status" -> status)))
  }
  def close(): Unit = out.close()
}
