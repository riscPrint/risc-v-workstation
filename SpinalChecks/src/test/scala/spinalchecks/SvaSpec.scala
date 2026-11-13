package spinalchecks

import org.scalatest.funsuite.AnyFunSuite

class SvaSpec extends AnyFunSuite {
  import Sva._
  test("emit finite properties with explicit clocks and reset") {
    val request = signal("req").sequence
    val response = signal("ack").sequence
    assert(request.implies(response, overlap = false).assertOn("response", signal("clk"), Some(signal("rst"))).startsWith(
      "response: assert property (@(posedge clk) disable iff (rst) (req) |=> (ack));"))
    assert(signal("data").stable.sequence.property.assertOn("hold", signal("clk")).contains("$stable(data)"))
  }
  test("resolve final names from an elaborated Spinal design") {
    import spinal.core.{assert => _, _}
    class Tiny extends Component {
      val io = new Bundle { val req = in Bool(); val ack = out Bool() }
      io.ack := RegNext(io.req) init(False)
      val contract = signal(io.req).sequence.implies(signal(io.ack).sequence, overlap = false)
    }
    val directory = java.nio.file.Files.createTempDirectory("sva-names-")
    val report = SpinalConfig(targetDirectory = directory.toString).generateVerilog(new Tiny)
    val rendered = report.toplevel.contract.assertOn("response", signal("clk"))
    assert(rendered.contains("(io_req) |=> (io_ack)"))
    assert(rendered.contains("rvw-source: SvaSpec.scala:"))
    val paths = java.nio.file.Files.walk(directory)
    try paths.sorted(java.util.Comparator.reverseOrder()).forEach(p => java.nio.file.Files.delete(p))
    finally paths.close()
  }
  test("retain finite composition and refuse unsafe names or bounds") {
    val a = signal("a").sequence
    assert(a.thenAfter(2, a).repeat(2).firstMatch.render == "first_match(((a) ##2 (a))[*2:2])")
    intercept[IllegalArgumentException](signal("a; bad"))
    assert(signal("data").past(2).render == "$past(data, 2)")
    intercept[IllegalArgumentException](signal("data").past(0))
    intercept[IllegalArgumentException](a.repeat(0))
    intercept[IllegalArgumentException](a.thenAfter(65, a))
  }
  test("emit explicit unbounded strength and until completion semantics") {
    val a = signal("a")
    val b = signal("b")
    assert(a.eventually.render == "s_eventually (a)")
    assert(a.until(b).render == "(a) until (b)")
    assert(a.untilWith(b, strong = true).render == "(a) s_until_with (b)")
    assert(a.sequence.implies(b.eventually, overlap = false).render == "(a) |=> (s_eventually (b))")
    assert(a.sequence.thenEventually(2, b.sequence).strong.render == "strong((a) ##[2:$] (b))")
    assert(a.sequence.repeatForever().weak.render == "weak((a)[*0:$])")
    assert(a.sequence.gotoRepeat(1, 3).render == "(a)[->1:3]")
    assert(a.sequence.nonConsecutive(2).render == "(a)[=2:2]")
    intercept[IllegalArgumentException](a.sequence.gotoRepeat(0))
    intercept[IllegalArgumentException](a.sequence.nonConsecutive(3, 2))
    intercept[IllegalArgumentException](a.sequence.repeatForever(65))
    intercept[IllegalArgumentException](a.sequence.thenEventually(-1, b.sequence))
  }
}

/** Run without sbt after Test/compile, for a small native emission smoke. */
object SvaEmitSmoke {
  def main(args: Array[String]): Unit = {
    import Sva._
    val req = signal("req").sequence
    val ack = signal("ack").sequence
    write(java.nio.file.Paths.get(args(0)), Seq(
      req.implies(ack, overlap = false).assertOn("response", signal("clk")),
      signal("data").stable.sequence.property.coverOn("stable_data", signal("clk"))))
  }
}

/** Emit the unbounded forms through the public API for native frontend tests. */
object SvaUnboundedEmitSmoke {
  def main(args: Array[String]): Unit = {
    import Sva._
    val req = signal("req").sequence
    val a = signal("a")
    val b = signal("b")
    val clock = signal("clk")
    write(java.nio.file.Paths.get(args(0)), Seq(
      req.implies(b.eventually).assertOn("eventual", clock),
      req.implies(a.until(b)).assertOn("weak_until", clock),
      req.implies(a.untilWith(b, strong = true)).assertOn("strong_until_with", clock),
      req.implies(literal(true).sequence.thenEventually(1, b.sequence).strong).assertOn("delay", clock),
      req.implies(a.sequence.repeatForever(1).thenAfter(1, b.sequence).strong).assertOn("consecutive", clock),
      req.implies(b.sequence.gotoRepeat(1, 2).thenAfter(1, a.sequence).strong).assertOn("goto_range", clock),
      req.implies(b.sequence.nonConsecutive(1, 2).thenAfter(1, a.sequence).strong).assertOn("nonconsecutive_range", clock),
      req.implies(b.sequence.gotoRepeat(2).weak).assertOn("weak_count", clock)))
  }
}
