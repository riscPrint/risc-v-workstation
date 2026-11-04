package riscvsim
import org.scalatest.funsuite.AnyFunSuite
class ProgressMonitorSpec extends AnyFunSuite {
  test("retries do not hide livelock and other completions do not hide starvation") {
    val m = new ProgressMonitor(10, 2, "round robin, response within 10 cycles")
    m.request("old", 0)
    for (c <- 1L to 10L) {
      m.retry("old", c); m.request("other", c); m.complete("other", c)
    }
    intercept[IllegalArgumentException](m.retry("old", 11))
  }
  test("resource exhaustion and cyclic waits fail without an unbounded proof claim") {
    val m = new ProgressMonitor(5, 2, "responses accepted within five cycles")
    m.request("A waits B", 0); m.request("B waits A", 0)
    intercept[IllegalArgumentException](m.request("third", 0))
    m.check(5)
    intercept[IllegalArgumentException](m.check(6))
    intercept[IllegalArgumentException](m.finish(6))
  }
  test("bounded completion at the deadline succeeds; unfinished campaign fails") {
    val m = new ProgressMonitor(5, 1, "bounded arbitration")
    m.request("a", 0)
    intercept[IllegalArgumentException](m.finish(1))
    m.complete("a", 5); m.finish(5)
    intercept[IllegalArgumentException](m.complete("a", 6))
  }
}
