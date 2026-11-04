package spinalchecks
import spinal.core._
import org.scalatest.funsuite.AnyFunSuite
class CsrChecksSpec extends AnyFunSuite with ApplicationTest {
  class Ref extends ApplicationRef {
    val state = Reg(Bits(4 bits)).init(0)
    val next = Bits(4 bits)
    next := state
    when(write && privilege === 3 && data(1 downto 0) =/= B(3, 2 bits)) { next := (state & B(12, 4 bits)) | (data & B(3, 4 bits)) }
    state := (next & ~hwClear) | hwSet
    CsrChecks.bind("status", CsrModel(1, 4, 0, 3, 3, Seq(0, 1, 2, 8, 9, 10).map(BigInt(_))), state ^ Mux(corrupt, B(1, 4 bits), B(0, 4 bits)),
      read, write, data, privilege, (privilege =/= 3) ^ corrupt, hwSet, hwClear)
  }
  test("CSR legal reset, WPRI, access and concurrent updates; state/access faults fire") {
    exercise("csr_ref", Set("csr.state", "csr.access"))(new Ref)
  }
  test("reject unsupported or ambiguous project intent") { intercept[IllegalArgumentException](CsrModel(2, 4, 0, 3, 3)) }
}
