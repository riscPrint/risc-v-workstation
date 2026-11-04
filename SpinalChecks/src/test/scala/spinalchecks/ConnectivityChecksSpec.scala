package spinalchecks
import spinal.core._
import org.scalatest.funsuite.AnyFunSuite
class ConnectivityChecksSpec extends AnyFunSuite with ApplicationTest {
  class Ref extends ApplicationRef {
    val delayed = RegNext(data)
    ConnectivityChecks.bind("wire", data, data ^ Mux(corrupt, B(1, 4 bits), B(0, 4 bits)), read, 0)
    ConnectivityChecks.bind("pipeline", data, delayed ^ Mux(corrupt, B(1, 4 bits), B(0, 4 bits)), write, 1)
  }
  test("enabled zero/one-cycle transfers pass; broken value transfers fire") {
    exercise("connectivity_ref", Set("connectivity.value"))(new Ref)
  }
}
