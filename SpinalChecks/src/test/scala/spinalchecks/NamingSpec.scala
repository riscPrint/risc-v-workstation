package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.lib._

import scala.io.Source

/** Round-2 review (2026-10-21): components created inside a loop body have no name until Spinal's name
  * allocation, after the checks are inserted. The report wrote `tile.frontend..io_x` (empty path
  * segment), which `rvw formal xprop --checks` rejected. */
class NamingSpec extends AnyFunSuite {
  class Stage extends Component {
    val io = new Bundle { val in = slave(Stream(UInt(8 bits))); val out = master(Stream(UInt(8 bits))) }
    io.out << io.in.m2sPipe()
  }
  class Wrap extends Component {
    val io = new Bundle { val in = slave(Stream(UInt(8 bits))); val out = master(Stream(UInt(8 bits))) }
    var s: Stream[UInt] = io.in
    for (_ <- 0 until 2) { val st = new Stage; st.io.in << s; s = st.io.out } // unnamed children
    io.out << s
  }
  class Top extends Component {
    val io = new Bundle { val in = slave(Stream(UInt(8 bits))); val out = master(Stream(UInt(8 bits))) }
    val wrap = new Wrap
    wrap.io.in << io.in
    io.out << wrap.io.out
  }

  test("report paths are the final instance names, never an empty segment") {
    val dir = "generated/naming"
    val (cfg, result) = SpinalChecks.install(SpinalConfig(targetDirectory = dir), ChecksConfig(mode = Mode.Monitor))
    cfg.generateVerilog(new Top)
    val json = Source.fromFile(result.reportFile).mkString
    val verilog = Source.fromFile(s"$dir/Top.v").mkString
    val quoted = "\"([^\"]*)\"".r.findAllMatchIn(json).map(_.group(1)).toSeq
    val bad = quoted.filter(q => q.contains("..") || q.endsWith(".") && q.length > 1 || q.startsWith("."))
    assert(bad.isEmpty, bad.distinct.mkString(", "))
    // Channel paths name instances that exist in the Verilog (Spinal calls them `stage`, `stage_1`).
    val paths = "\"path\": \"([^\"]*)\"".r.findAllMatchIn(json).map(_.group(1)).toSet
    val stages = paths.filter(_.contains(".stage"))
    assert(stages.size == 2, paths)
    // Since round 13 each Stage carries its own check ids, so Spinal keeps two definitions (`Stage_1`).
    for (p <- stages; Array(w, st) = p.split('.'))
      assert(s"(?s).*\\bWrap(_\\d+)? $w \\(.*".r.pattern.matcher(verilog).matches() && s"(?s).*\\bStage(_\\d+)? $st \\(.*".r.pattern.matcher(verilog).matches(), (p, paths))
    // Ids never have an empty segment either (they are taken before name allocation).
    assert(!result.records.exists(_.id.contains("..")), result.records.map(_.id))
    assert(result.records.exists(_.id.contains(".stage.")), result.records.map(_.id))
  }

  /** Round 13 (/tmp/review13-c/reproduce-check-ids.sh): both unnamed `Stage`s had the id
    * `stream.valid_hold:wrap.stage.io_in`, so one exact waiver waived the check in both instances. */
  test("unnamed sibling instances get distinct ids; one exact waiver waives exactly one check") {
    def ids(waivers: Seq[Waiver]) = {
      val (cfg, result) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/naming-ids"),
        ChecksConfig(mode = Mode.Monitor, waivers = waivers))
      cfg.generateVerilog(new Top)
      result.records.toSeq
    }
    val all = ids(Nil)
    assert(all.map(_.id).distinct.size == all.size, all.map(_.id))
    val holds = all.filter(r => r.kind == Kind.StreamValidHold && r.id.contains(".stage") && r.id.endsWith(".io_in")).map(_.id).toSet
    assert(holds == Set("stream.valid_hold:wrap.stage.io_in", "stream.valid_hold:wrap.stage_1.io_in"), holds)
    val waived = ids(Seq(Waiver("stream.valid_hold:wrap.stage.io_in", "one instance"))).filter(_.status == "waived")
    assert(waived.map(_.id) == Seq("stream.valid_hold:wrap.stage.io_in"), waived.map(_.id))
    // Each id names one instance; the report path is that instance's final Verilog name (Spinal may add
    // suffixes the ids do not have: `wrap_1.stage_2`).
    val finals = all.filter(r => holds.contains(r.id)).map(r => SpinalChecks.instancePath(r.component))
    assert(finals.distinct.size == 2 && finals.forall(SpinalCompat.matches("wrap(_\\d+)?\\.stage(_\\d+)?".r, _)), finals)
    // A glob still reaches every instance it matches.
    assert(ids(Seq(Waiver("stream.valid_hold:wrap.stage*.io_in", "both"))).count(_.status == "waived") == 2)
  }

  class Indexes extends Component {
    val io = new Bundle {
      val a, b = in UInt(2 bits)
      val x, y = out UInt(8 bits)
    }
    val v = Vec(Seq(U(1, 8 bits), U(2, 8 bits), U(3, 8 bits)))
    io.x := v((io.a + io.b).resize(2)) // two selects without a name: both fall back to `index`
    io.y := v((io.a - io.b).resize(2))
  }

  test("unnamed objects in one component get distinct ids") {
    val (cfg, result) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/naming-objects"),
      ChecksConfig(mode = Mode.Monitor))
    cfg.generateVerilog(new Indexes)
    val vec = result.records.filter(_.kind == Kind.VecIndex).map(_.id).toSet
    assert(vec == Set("vec.index:index_of3", "vec.index:index_of3_1"), result.records.map(_.id))
  }

  test("a repeated id is an error, not a check that a waiver reaches twice") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/naming-dup"), ChecksConfig(
      mode = Mode.Monitor, progress = Seq(ProgressSpec("p", "io_out_valid", 8), ProgressSpec("p", "io_out_valid", 9))))
    val e = intercept[Throwable](cfg.generateVerilog(new Stage))
    def chain(t: Throwable): Seq[String] = if (t == null) Nil else String.valueOf(t.getMessage) +: chain(t.getCause)
    assert(chain(e).exists(_.contains("duplicate check ids: progress.watchdog:p (2x)")), chain(e))
  }
}
