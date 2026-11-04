package spinalchecks
import spinal.core._
import org.scalatest.funsuite.AnyFunSuite
class RegisterChecksSpec extends AnyFunSuite with ApplicationTest {
  class Ref extends ApplicationRef {
    val state = Reg(Bits(4 bits)).init(15)
    // Separate per-bit reference implementation.
    for (i <- 0 until 4) {
      val next = Bool()
      next := state(i)
      if (i == 3) when(read) { next := False }
      if (i < 2) when(write && strobes(i)) { next := data(i) }
      if (i == 2) when(write && strobes(i) && data(i)) { next := False }
      when(hwClear(i)) { next := False }
      when(hwSet(i)) { next := True }
      state(i) := next
    }
    RegisterChecks.bind("device", RegisterModel(1, 4, 15, 3, 4, 8),
      state ^ Mux(corrupt, B(1, 4 bits), B(0, 4 bits)), read, write, data, strobes, hwSet, hwClear)
  }
  test("device legal read-clear, W1C, strobes, simultaneous set/clear; fault fires") {
    exercise("register_ref", Set("register.state"))(new Ref)
  }
  test("reject unsupported or ambiguous project intent") { intercept[IllegalArgumentException](RegisterModel(1, 4, 0, 3, 1, 0)) }
}
