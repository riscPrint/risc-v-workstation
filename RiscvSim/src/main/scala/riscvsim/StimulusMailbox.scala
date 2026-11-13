package riscvsim

import java.io.File

/** A loaded `rvw.stimulus/1` file: ordered device events, each served through a RAM mailbox. */
case class StimulusFile(file: File, sha256: String, events: Seq[ujson.Obj], text: String = "")

object StimulusMailbox {
  /** `text` is the option value as given; C1 echoes it as `stimulus_file`. */
  def load(file: File, text: String = ""): StimulusFile = {
    val bytes = java.nio.file.Files.readAllBytes(file.toPath)
    val doc = try ujson.read(bytes).obj catch {
      case e: Exception => throw new Cli.UsageError(s"--stimulus-file: ${e.getMessage}")
    }
    if (!doc.get("schema").exists(_.strOpt.contains("rvw.stimulus/1")))
      throw new Cli.UsageError("--stimulus-file: schema must be rvw.stimulus/1")
    val events = doc("events").arr.toSeq.map(_("payload").obj)
    val steps = events.map(_("step").num)
    if (steps.isEmpty || steps.exists(s => s <= 0 || s % 1 != 0) || steps != steps.distinct.sorted)
      throw new Cli.UsageError("--stimulus-file: steps must be positive integers in increasing order")
    if (events.exists(e => !e.get("request_symbol").exists(_.strOpt.contains("stimulus_step")) ||
        !e.get("ack_symbol").exists(_.strOpt.contains("stimulus_ack"))))
      throw new Cli.UsageError("--stimulus-file: events must use the stimulus_step/stimulus_ack mailbox")
    StimulusFile(file, ElfFile.sha256(bytes), events.map(e => ujson.Obj.from(e)), if (text.nonEmpty) text else file.getPath)
  }
}

/** Serves `rvw.stimulus/1` events in order. The program writes a step number to `stimulus_step`;
  * when it names the next event, `drive` applies the event, and after `settle_ticks` cycles
  * (default 0) `acknowledge` writes the step to `stimulus_ack`. Other requests are ignored.
  * No core or device names live here: the adapter supplies both callbacks. */
final class StimulusMailbox(stimulus: StimulusFile, drive: ujson.Obj => Unit, acknowledge: Long => Unit) {
  private var next = 0
  private var pending = Option.empty[(Long, Long)] // (due cycle, step)

  /** A store of `value` to the request word at `cycle`. Returns true when it started an event. */
  def request(cycle: Long, value: BigInt): Boolean = {
    if (pending.nonEmpty || next >= stimulus.events.size) return false
    val event = stimulus.events(next)
    val step = event("step").num.toLong
    if (value != BigInt(step)) return false
    drive(event)
    next += 1
    pending = Some((cycle + event.value.get("settle_ticks").map(_.num.toLong).getOrElse(0L), step))
    true
  }

  /** Call once per sampled cycle: writes a due acknowledgement. */
  def tick(cycle: Long): Unit = pending.foreach { case (due, step) =>
    if (cycle >= due) { acknowledge(step); pending = None }
  }

  def served: Int = next
  def complete: Boolean = next == stimulus.events.size && pending.isEmpty
}
