package riscvsim
import org.scalatest.funsuite.AnyFunSuite
class FairnessMonitorSpec extends AnyFunSuite {
  test("environment enable fairness is measured separately from arbitration") {
    val m = new FairnessMonitor(Set("a","b"),2,2)
    m.sample(0,Set("a","b"),Set("a"),Set("a"))
    m.sample(1,Set("b"),Set("b"),Set.empty)
    m.sample(2,Set("b"),Set("b"),Set("b"))
    assert(m.maxDisabled == 1 && m.maxGrantWait == 2)
    m.finish(Set("a","b"))
  }
  test("unfair environment and arbiter produce different failures") {
    for (environment <- Seq(true,false)) {
      val m = new FairnessMonitor(Set("a"),2,2)
      val enabled = if (environment) Set.empty[String] else Set("a")
      m.sample(0,Set("a"),enabled,Set.empty); m.sample(1,Set("a"),enabled,Set.empty)
      val e = intercept[IllegalArgumentException](m.sample(2,Set("a"),enabled,Set.empty))
      assert(e.getMessage.contains(if (environment) "environment fairness" else "arbiter fairness"))
    }
  }
  test("missing samples and unobserved clients cannot earn fairness") {
    val m = new FairnessMonitor(Set("a","b"),2,2)
    m.sample(0,Set("a"),Set("a"),Set("a"))
    intercept[IllegalArgumentException](m.sample(2,Set.empty,Set.empty,Set.empty))
    intercept[IllegalArgumentException](m.finish(Set("a","b")))
  }
  test("resource cycles, self waits and acyclic exhaustion are distinct") {
    ResourceWaitMonitor.check(Map("r0" -> "a","r1" -> "b"),Map("c" -> Set("r0","r1")))
    intercept[IllegalArgumentException](ResourceWaitMonitor.check(Map("r0" -> "a"),Map("a" -> Set("r0"))))
    intercept[IllegalArgumentException](ResourceWaitMonitor.check(Map("r0" -> "a","r1" -> "b"),Map("a" -> Set("r1"),"b" -> Set("r0"))))
  }
}
