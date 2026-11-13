package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class HartLifecycleObserverSpec extends AnyFunSuite {
  def observer = new HartLifecycleObserver(Set(0, 1, 2), Set(0), 10, "project HSM service")
  test("independent HSM start stop restart and coalesced cross-hart IPIs") {
    val o = observer
    o.start(0, 1, 0x1000, 7, 0)
    intercept[IllegalArgumentException](o.started(1, 0x1000, 8, 1))
    o.started(1, 0x1000, 7, 1)
    o.sendIpi(0, Set(1, 2), 2); o.sendIpi(0, Set(1), 2)
    o.observeIpi(1, true, 2); o.observeIpi(0, false, 2)
    o.clearIpi(1, 3); o.observeIpi(1, false, 3); o.observeIpi(2, true, 3)
    o.stop(1, 4); o.stopped(1, 5)
    o.start(0, 1, 0x2000, 9, 6); o.started(1, 0x2000, 9, 7)
    o.finish(8, Map(0 -> "started", 1 -> "started", 2 -> "stopped"))
  }
  test("shared interrupt claim has one owner and requires matching completion") {
    val o = observer
    o.start(0, 1, 0x1000, 0, 0); o.started(1, 0x1000, 0, 1)
    o.claim(0, 5, 2)
    intercept[IllegalArgumentException](o.claim(1, 5, 2))
    intercept[IllegalArgumentException](o.completeInterrupt(1, 5, 3))
    o.completeInterrupt(0, 5, 3)
    o.claim(1, 5, 4); o.completeInterrupt(1, 5, 5)
  }
  test("pending transitions time out and reset preserves shared IPI state by default") {
    val o = observer
    o.start(0, 1, 0x1000, 0, 0)
    intercept[IllegalArgumentException](o.check(11))
    var reset = -1
    val r = new HartLifecycleObserver(Set(0, 1), Set(0), 10, "service", h => reset = h)
    r.start(0, 1, 0x1000, 0, 0); r.sendIpi(0, Set(1), 1); r.reset(1, 2)
    assert(r.epoch(1) == 1 && reset == 1)
    r.observeIpi(1, true, 3); r.clearIpi(1, 3); r.observeIpi(1, false, 3)
    r.finish(4, Map(0 -> "started", 1 -> "stopped"))
  }
}
