package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class ResetScheduleSpec extends AnyFunSuite {
  test("delay, actual pulse, observations and repeated reset") {
    var pin = false
    var preparations = 0
    var releases = 0
    val reset = new ResetSchedule(3, 2, v => pin = v,
      () => ujson.Obj("state" -> ujson.Obj("privilege" -> 3), "valid" -> ujson.Obj("request_valid" -> false)),
      () => preparations += 1, () => releases += 1)
    reset.request(10, 1)
    reset.tick(11)
    assert(!pin && reset.busy)
    reset.tick(12)
    assert(pin && reset.active && preparations == 1)
    intercept[IllegalArgumentException](reset.request(12, 2))
    (13L to 16L).foreach(reset.tick)
    assert(!pin && !reset.busy && releases == 1)
    assert(reset.observations.arr.head.arr.size == 4)
    assert(reset.observations.arr.head.arr.last("asserted").bool == false)
    reset.request(20, 2)
    (21L to 26L).foreach(reset.tick)
    assert(reset.observations.arr.size == 2 && preparations == 2 && releases == 2)
  }
  test("invalid timing is refused") {
    intercept[IllegalArgumentException](new ResetSchedule(1, 2, _ => (), () => ujson.Obj(), () => (), () => ()))
    intercept[IllegalArgumentException](new ResetSchedule(3, 0, _ => (), () => ujson.Obj(), () => (), () => ()))
  }
}
