package riscvsim

/** Separate sampled environment enable fairness from arbiter grant fairness.
  * Every sample is a clock edge. Repeated disabled cycles cannot hide starvation.
  * Bounds apply to consecutive disabled cycles and enabled grant opportunities. */
final class FairnessMonitor(clients: Set[String], enableBound: Long, grantBound: Long) {
  require(clients.nonEmpty && enableBound > 0 && grantBound > 0)
  private var cycle = -1L
  private var disabled = Map.empty[String, Long].withDefaultValue(0L)
  private var waiting = Map.empty[String, Long].withDefaultValue(0L)
  private var sampled = Set.empty[String]
  private var grants = Map.empty[String, Long].withDefaultValue(0L)
  var maxDisabled: Long = 0L
  var maxGrantWait: Long = 0L
  def sample(at: Long, offered: Set[String], enabled: Set[String], granted: Set[String]): Unit = {
    require(at >= 0 && (cycle == -1 || at == cycle + 1), "missing fairness sample")
    require((offered ++ enabled ++ granted).subsetOf(clients), "unknown fairness client")
    require(granted.subsetOf(offered intersect enabled), "grant without enabled request")
    cycle = at; sampled ++= offered
    for (id <- clients) {
      if (!offered(id)) { disabled += id -> 0L; waiting += id -> 0L }
      else {
        disabled += id -> (if (enabled(id)) 0L else disabled(id) + 1)
        maxDisabled = maxDisabled.max(disabled(id))
        require(disabled(id) <= enableBound, s"environment fairness exceeded: $id")
        if (enabled(id)) {
          waiting += id -> (waiting(id) + 1)
          maxGrantWait = maxGrantWait.max(waiting(id))
          require(waiting(id) <= grantBound, s"arbiter fairness exceeded: $id")
        }
        if (granted(id)) { waiting += id -> 0L; grants += id -> (grants(id) + 1) }
      }
    }
  }
  def finish(required: Set[String]): Unit = {
    require(required.nonEmpty && required.subsetOf(sampled) && required.forall(grants(_) > 0), "missing fairness observations")
    require(disabled.values.forall(_ == 0) && waiting.values.forall(_ == 0), "pending fairness obligations")
  }
}
