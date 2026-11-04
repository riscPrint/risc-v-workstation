package riscvsim

import scala.collection.mutable

/** Project-normalized TileLink-C permission transitions, after accepted channel handshakes.
  * N = None, B = Branch (read), T = Trunk (exclusive). This is a permission
  * scoreboard, not a complete TileLink channel/beat legality checker. */
final class CoherenceMonitor(lineBytes: Int, clients: Set[Int]) {
  require(lineBytes > 0 && (lineBytes & (lineBytes - 1)) == 0 && clients.nonEmpty)
  private val lines = mutable.Map.empty[(Int, Int), String]
  private def key(client: Int, address: Int): (Int, Int) = {
    require(clients(client) && address >= 0 && address % lineBytes == 0)
    client -> address
  }
  def state(client: Int, address: Int): String = lines.getOrElse(key(client, address), "N")
  /** A grant may not become visible until conflicting probe acknowledgments complete. */
  def grant(client: Int, address: Int, permission: String): Unit = {
    val k = key(client, address)
    require(Set("B", "T")(permission))
    require(state(client, address) != "T", "grant to existing trunk")
    val others = clients.filter(_ != client).map(state(_, address))
    if (permission == "T") require(others.forall(_ == "N"), "exclusive grant before invalidation")
    else require(!others.contains("T"), "branch grant before intervention")
    lines(k) = permission
  }
  /** Completed ProbeAck/Release. Data correctness is checked by CacheScoreboard. */
  def shrink(client: Int, address: Int, from: String, to: String, dirty: Boolean, hasData: Boolean): Unit = {
    val k = key(client, address)
    require(state(client, address) == from, "stale permission transition")
    require(Set(("T", "B"), ("T", "N"), ("B", "N"), ("B", "B"), ("N", "N"))((from, to)),
      "illegal shrink")
    require(!dirty || (from == "T" && hasData), "dirty owner lost data")
    lines(k) = to
  }
}
