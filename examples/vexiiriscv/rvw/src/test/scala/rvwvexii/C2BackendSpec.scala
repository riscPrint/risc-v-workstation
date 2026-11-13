package rvwvexii

import org.scalatest.funsuite.AnyFunSuite
import riscvsim.RvfiRecord
import scala.collection.mutable.ArrayBuffer

class C2BackendSpec extends AnyFunSuite {
  test("lookahead holds the current cycle until the observed next PC arrives") {
    var cycle = 1L
    val rows = ArrayBuffer.empty[RvfiRecord]
    val backend = new C2Backend(32, () => cycle, () => 3, () => (BigInt(0), BigInt(0)),
      r => rows += r, (_, _, _, _) => (), (_, _, _) => ())
    backend.commit(0, 0x80000000L, 0x13)
    assert(rows.isEmpty && backend.pendingCycle.contains(1))
    cycle = 4
    backend.commit(0, 0x80000004L, 0x13)
    assert(rows.size == 1 && rows.head.pcNext == BigInt("80000004", 16))
    assert(rows.head.cycle == 1 && backend.pendingCycle.contains(4))
    backend.drain()
    assert(rows.map(_.order).toSeq == Seq(BigInt(0), BigInt(1)))
    assert(backend.pendingCycle.isEmpty)
  }

  test("interrupt trap value is the observed value, without a fabricated zero") {
    val observed = ArrayBuffer.empty[BigInt]
    val backend = new C2Backend(32, () => 10L, () => 3, () => (BigInt(0), BigInt(0x123)),
      _ => (), (_, _, value, _) => observed += value, (_, _, _) => ())
    backend.trap(0, true, 7)
    assert(observed.toSeq == Seq(BigInt(0x123)))
  }
}
