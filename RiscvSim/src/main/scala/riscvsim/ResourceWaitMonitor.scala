package riscvsim

/** A sampled resource graph, independent of request-age watchdogs.
  * Each exclusive resource has one observed owner. Edges come from blocked RTL
  * requests, not from a test's desired schedule. Cycles are bounded observations. */
object ResourceWaitMonitor {
  def check(owners: Map[String, String], waits: Map[String, Set[String]]): Unit = {
    require(owners.forall { case (r,o) => r.nonEmpty && o.nonEmpty })
    require(waits.forall { case (o,rs) => o.nonEmpty && rs.forall(_.nonEmpty) })
    val edges = waits.map { case (owner, resources) => owner -> resources.flatMap(owners.get) }
    def visit(node: String, path: Set[String]): Unit = {
      require(!path(node), s"cyclic resource dependency: ${(path + node).toSeq.sorted.mkString(",")}")
      edges.getOrElse(node,Set.empty).foreach(next => visit(next,path + node))
    }
    edges.keys.foreach(n => visit(n,Set.empty))
  }
}
