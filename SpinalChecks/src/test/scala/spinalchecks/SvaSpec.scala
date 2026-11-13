package spinalchecks

import org.scalatest.funsuite.AnyFunSuite

class SvaSpec extends AnyFunSuite {
  import Sva._
  test("emit finite properties with explicit clocks and reset") {
    val request = signal("req").sequence
    val response = signal("ack").sequence
    assert(request.implies(response, overlap = false).assertOn("response", signal("clk"), Some(signal("rst"))) ==
      "response: assert property (@(posedge clk) disable iff (rst) (req) |=> (ack));")
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
    val paths = java.nio.file.Files.walk(directory)
    try paths.sorted(java.util.Comparator.reverseOrder()).forEach(p => java.nio.file.Files.delete(p))
    finally paths.close()
  }
  test("retain finite composition and refuse unsafe names or bounds") {
    val a = signal("a").sequence
    assert(a.thenAfter(2, a).repeat(2).firstMatch.render == "first_match(((a) ##2 (a))[*2:2])")
    intercept[IllegalArgumentException](signal("a; bad"))
    intercept[IllegalArgumentException](a.repeat(0))
    intercept[IllegalArgumentException](a.thenAfter(65, a))
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
