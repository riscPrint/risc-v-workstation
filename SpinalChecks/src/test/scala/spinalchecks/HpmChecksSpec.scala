package spinalchecks
import spinal.core._
import org.scalatest.funsuite.AnyFunSuite
class HpmChecksSpec extends AnyFunSuite with ApplicationTest {
  class Ref extends ApplicationRef {
    val count = Reg(UInt(4 bits)).init(0)
    when(permitted && !inhibit) { count := count + 1 }
    when(write) { count := data.asUInt }
    HpmChecks.bind("events", HpmModel(1, 4, 0, "one independently driven event each cycle"),
      count ^ Mux(corrupt, U(1, 4 bits), U(0, 4 bits)), U(1, 1 bits), inhibit, permitted, write, data.asUInt)
  }
  test("HPM legal inhibit, filter, writes and wrap; wrong count fires") {
    exercise("hpm_ref", Set("hpm.count"))(new Ref)
  }
  test("reject unsupported or ambiguous project intent") { intercept[IllegalArgumentException](HpmModel(1, 4, 0, "")) }
}
