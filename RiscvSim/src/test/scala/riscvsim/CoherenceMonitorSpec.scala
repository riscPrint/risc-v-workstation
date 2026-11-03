package riscvsim
import org.scalatest.funsuite.AnyFunSuite
class CoherenceMonitorSpec extends AnyFunSuite {
  test("intervention, sharing, invalidation and eviction preserve single writer") {
    val m = new CoherenceMonitor(64, Set(0, 1))
    m.grant(0, 0, "T")
    intercept[IllegalArgumentException](m.grant(1, 0, "B"))
    intercept[IllegalArgumentException](m.shrink(0, 0, "T", "B", true, false))
    m.shrink(0, 0, "T", "B", true, true); m.grant(1, 0, "B")
    intercept[IllegalArgumentException](m.grant(1, 0, "T"))
    m.shrink(0, 0, "B", "N", false, false); m.grant(1, 0, "T")
    intercept[IllegalArgumentException](m.shrink(1, 0, "B", "N", false, false))
    m.shrink(1, 0, "T", "N", true, true)
    assert(m.state(0, 0) == "N" && m.state(1, 0) == "N")
  }
  test("racing requests cannot both gain trunk under delayed probe response") {
    val m = new CoherenceMonitor(64, Set(0, 1))
    m.grant(0, 64, "T")
    for (_ <- 0 until 10) intercept[IllegalArgumentException](m.grant(1, 64, "T"))
    m.shrink(0, 64, "T", "N", false, false); m.grant(1, 64, "T")
    intercept[IllegalArgumentException](m.grant(0, 64, "T"))
  }
}
