package spinalchecks

import java.nio.file.{Files, Paths}

import spinal.core._
import spinal.core.sim._

/** Simulation side of Monitor mode: reads back which checks fired. Call from inside a simulation
  * thread (e.g. at the end of `doSim`), with the simulated toplevel. */
object ChecksSim {
  case class Firing(check: CheckRecord, count: Int, firstCycle: Long)

  private def requireMonitors(r: ChecksResult): Unit =
    require(r.config.mode != Mode.Assert && r.inserted.forall(c =>
      c.fired != null && c.count != null && c.firstCycle != null),
      "check monitoring is unavailable; use monitor or both mode for simulation reports")

  /** A program pass also needs zero generated check failures. Preserve other failure statuses. */
  def checkedStatus(status: String, fs: Seq[Firing]): String =
    if (status == "pass" && fs.nonEmpty) "fail" else status

  def firings(top: Component): Seq[Firing] = {
    val r = SpinalChecks.result(top)
    requireMonitors(r)
    r.inserted.flatMap { c =>
      if (c.fired.toBoolean) Some(Firing(c, c.count.toInt, c.firstCycle.toLong)) else None
    }
  }

  /** `rvw.checks-run/1`: the run's firing checks, plus caller metadata (test name, status, seed...).
    * Pure: `fs` comes from [[firings]], read inside the simulation. */
  def runReport(r: ChecksResult, fs: Seq[Firing], meta: Seq[(String, Json.V)], activations: Seq[Json.V] = Nil): String = {
    import Json._
    requireMonitors(r)
    val checkedMeta = meta.map {
      case ("status", Str(status)) => "status" -> Str(checkedStatus(status, fs))
      case field => field
    }
    Json.write(obj(Seq[(String, V)](
      "schema" -> "rvw.checks-run/1",
      "toplevel" -> r.top.definitionName,
      "checks_report" -> r.reportFile,
      "inserted" -> r.inserted.size,
      "fired" -> fs.size) ++ checkedMeta ++ Seq[(String, V)](
      "activations" -> arr(activations),
      "firings" -> arr(fs.sortBy(_.firstCycle).map(f => obj(
        "id" -> f.check.id, "kind" -> f.check.kind, "count" -> f.count, "count_saturated" -> (f.count == 0xffff),
        "first_cycle" -> f.firstCycle, "fail_signal" -> Option(f.check.failName).map(n => SpinalChecks.qualify(SpinalChecks.instancePath(f.check.component), n)),
        "source" -> f.check.location.map(_.toString)): V))
    ): _*)) + "\n"
  }

  /** Reads the firings and writes the report; call inside the simulation. */
  def writeRunReport(top: Component, file: String, meta: Seq[(String, Json.V)] = Nil): Unit =
    {
      import Json._
      val r = SpinalChecks.result(top)
      val activations = r.inserted.map { c =>
        val hits = Option(c.activationCount).map(_.toLong)
        obj("id" -> c.id, "count" -> hits,
          "status" -> Str(hits.map(n => if (n > 0) "activated" else "no_activation").getOrElse("unmeasured"))): V
      }
      writeFile(file, runReport(r, firings(top), meta, activations))
    }

  def writeFile(file: String, text: String): Unit = {
    val p = Paths.get(file).toAbsolutePath
    Files.createDirectories(p.getParent)
    Files.write(p, text.getBytes("UTF-8"))
  }
}
