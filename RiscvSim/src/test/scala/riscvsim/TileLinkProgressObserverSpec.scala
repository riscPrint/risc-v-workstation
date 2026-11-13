package riscvsim

import org.scalatest.funsuite.AnyFunSuite
import spinal.lib.bus.tilelink.Opcode
import spinal.lib.bus.tilelink.sim._

class TileLinkProgressObserverSpec extends AnyFunSuite {
  def a(source: Int): TransactionA = { val t = new TransactionA; t.source=source; t.opcode=Opcode.A.ACQUIRE_BLOCK; t }
  def b: TransactionB = { val t = new TransactionB; t.source=0; t.address=64; t.opcode=Opcode.B.PROBE_BLOCK; t }
  def c(release: Boolean): TransactionC = {
    val t = new TransactionC; t.source=0; t.address=64
    t.opcode=if (release) Opcode.C.RELEASE_DATA else Opcode.C.PROBE_ACK_DATA; t
  }
  def d(source: Int, grant: Boolean = false, release: Boolean = false): TransactionD = {
    val t = new TransactionD; t.source=source; t.sink=2
    t.opcode=if (release) Opcode.D.RELEASE_ACK else if (grant) Opcode.D.GRANT_DATA else Opcode.D.ACCESS_ACK; t
  }
  def e: TransactionE = { val t = new TransactionE; t.sink=2; t }
  test("A retains its deadline through GrantAck and probes/releases remain separate") {
    var cycle = 0L
    val o = new TileLinkProgressObserver(10, 4, "bounded accepted-message service", () => cycle)
    o.onA(a(0)); cycle=1; o.onB(b); cycle=2; o.onC(c(false))
    cycle=3; o.onD(d(0, grant=true)); assert(o.outstanding==1)
    cycle=4; o.onE(e); o.onC(c(true)); cycle=5; o.onD(d(0, release=true))
    o.finish(Set("a","b","c_probe_ack","c_release","d_grant","d_release_ack","e"))
  }
  test("unrelated completions cannot renew an A deadline waiting for E") {
    var cycle = 0L
    val o = new TileLinkProgressObserver(10, 4, "service", () => cycle)
    o.onA(a(0)); cycle=1; o.onD(d(0, grant=true))
    for (n <- 2L to 10L) { cycle=n; o.onA(a(1)); o.onD(d(1)) }
    cycle=11
    val error=intercept[IllegalArgumentException](o.tick())
    assert(error.getMessage.contains("bounded forward progress"))
  }
  test("lost probe/release responses time out and empty evidence cannot pass") {
    var cycle = 0L
    val probe = new TileLinkProgressObserver(10, 4, "service", () => cycle)
    probe.onB(b); cycle=11; intercept[IllegalArgumentException](probe.tick())
    cycle=0
    val release = new TileLinkProgressObserver(10, 4, "service", () => cycle)
    release.onC(c(true)); cycle=11; intercept[IllegalArgumentException](release.tick())
    val empty = new TileLinkProgressObserver(10, 4, "service", () => cycle)
    intercept[IllegalArgumentException](empty.finish(Set("a")))
  }
  test("response identities and capacity are checked") {
    def fresh = new TileLinkProgressObserver(10, 2, "service", () => 0L)
    val unknownD = fresh; unknownD.onD(d(0)); intercept[IllegalArgumentException](unknownD.tick())
    val duplicate = fresh; duplicate.onA(a(0)); duplicate.onA(a(0)); intercept[IllegalArgumentException](duplicate.tick())
    val capacity = fresh; capacity.onA(a(0)); capacity.onB(b); capacity.tick()
    capacity.onC(c(true)); intercept[IllegalArgumentException](capacity.tick())
    val unknownE = fresh; unknownE.onE(e); intercept[IllegalArgumentException](unknownE.tick())
  }
  test("same-cycle callbacks can arrive before their prerequisites") {
    val o = new TileLinkProgressObserver(10, 4, "service", () => 0L)
    o.onE(e); o.onD(d(0, grant=true)); o.onC(c(false)); o.onB(b); o.onA(a(0))
    o.tick(); o.finish(Set("a", "b", "c_probe_ack", "d_grant", "e"))
  }
  test("same-cycle source and sink reuse complete the old request only") {
    var cycle = 0L
    val o = new TileLinkProgressObserver(10, 4, "service", () => cycle)
    o.onA(a(0)); o.tick()
    cycle=1; o.onA(a(0)); o.onE(e); o.onD(d(0, grant=true)); o.tick()
    assert(o.outstanding==1)
    cycle=2; o.onE(e); o.onD(d(0, grant=true)); o.tick()
    o.finish(Set("a", "d_grant", "e"))
    val q = new TileLinkProgressObserver(10, 4, "service", () => cycle)
    q.onA(a(0)); q.onA(a(1)); q.tick()
    cycle=3; q.onD(d(0, grant=true)); q.tick()
    cycle=4; q.onD(d(1, grant=true)); q.onE(e); q.tick()
    assert(q.outstanding==1)
    cycle=5; q.onE(e); q.finish(Set("e"))
  }
  test("a truncated ReleaseData cannot disappear before the complete-message callback") {
    var cycle = 0L
    val o = new TileLinkProgressObserver(10, 4, "service", () => cycle)
    val first = c(true)
    assert(SpinalCompat.intMember(first, "beat").forall(_ == 0))
    o.onBeatC(first); o.tick(); assert(o.outstanding==1)
    cycle=11; intercept[IllegalArgumentException](o.tick())
    cycle=0
    val complete = new TileLinkProgressObserver(10, 4, "service", () => cycle)
    complete.onD(d(0, release=true)); complete.onC(first); complete.onBeatC(first)
    complete.tick(); complete.finish(Set("c_release_complete", "d_release_ack"))
  }

}
