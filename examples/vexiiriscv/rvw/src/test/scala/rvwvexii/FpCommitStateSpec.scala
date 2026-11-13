package rvwvexii

import org.scalatest.funsuite.AnyFunSuite
import riscvsim.{FpCommitState, RvfiFpState, RvfiRecord}

class FpCommitStateSpec extends AnyFunSuite {
  private def row(order: Int, status: BigInt = 0x4000): RvfiRecord =
    RvfiRecord(BigInt(order), order.toLong, 0x53, false, false, false, 3, 2,
      0, 0, 0, 0, 0, 0, 0x80000000L + order * 4, 0, 0, 0, 0, 0, 0, false,
      csrState = Map(0x300 -> status), fpState = Some(RvfiFpState(false, 0, 0, 0, 0)))
  private def clock(c: FpCommitState, fcsr: Int, status: BigInt = 0x4000,
                    flags: Seq[(Int,BigInt)] = Nil, csrs: Seq[(Int,Int,BigInt)] = Nil,
                    dirty: Seq[Int] = Nil): Unit = c.observe(fcsr, status, flags, csrs, dirty)

  test("late flag effect follows its micro-op, not the instruction sampling the old CSR") {
    val c = new FpCommitState(64)
    c.allocate(1); c.allocate(2)
    clock(c, 0)
    c.retire(0, 1); c.retire(1, 2)
    clock(c, 16, flags = Seq(1 -> BigInt(16)))
    clock(c, 16)
    c.finish()
    assert(c.project(row(0)).fpState.get.flags == 16)
    assert(c.project(row(1)).fpState.get.flags == 16)
  }

  test("an unexplained physical CSR change is rejected") {
    val c = new FpCommitState(64)
    clock(c, 0)
    assertThrows[IllegalArgumentException](clock(c, 1))
  }

  test("lost actual flag accumulation is rejected rather than repaired") {
    val c = new FpCommitState(64); c.allocate(1)
    clock(c, 1)
    assertThrows[IllegalArgumentException](clock(c, 2, flags = Seq(1 -> BigInt(2))))
  }

  test("rounding writes preserve independently observed accumulated flags") {
    val c = new FpCommitState(64)
    c.allocate(1); c.allocate(2)
    clock(c, 1)
    clock(c, 0x61, csrs = Seq((1, 2, BigInt(3))))
    clock(c, 0x63, flags = Seq(2 -> BigInt(2)))
    clock(c, 0x63)
    c.retire(0, 1); c.retire(1, 2); c.finish()
    assert(c.project(row(0)).fpState.get.fcsr == 0x61)
    assert(c.project(row(1)).fpState.get.fcsr == 0x63)
  }

  test("software clears use actual post-write FCSR rather than retaining stale flags") {
    val c = new FpCommitState(64); c.allocate(1)
    clock(c, 31)
    clock(c, 0, csrs = Seq((1, 1, BigInt(0))))
    clock(c, 0)
    c.retire(0, 1); c.finish()
    assert(c.project(row(0)).fpState.get.fcsr == 0)
  }

  test("late FS dirty event changes its retirement and the following state") {
    val c = new FpCommitState(64); c.allocate(1); c.allocate(2)
    clock(c, 0)
    c.retire(0, 1); c.retire(1, 2)
    val dirty = (BigInt(1) << 63) | 0x6000
    clock(c, 0, status = dirty, dirty = Seq(1))
    clock(c, 0, status = dirty)
    c.finish()
    assert(c.project(row(0)).csrState(0x300) == dirty)
    assert(c.project(row(1)).csrState(0x300) == dirty)
  }

  test("software FS writes retain the actual post-write state") {
    val c = new FpCommitState(64); c.allocate(1)
    val dirty = (BigInt(1) << 63) | 0x6000
    clock(c, 0, status = dirty)
    clock(c, 0, status = 0x4000, csrs = Seq((1, 0x300, BigInt(0x4000))))
    clock(c, 0, status = 0x4000)
    c.retire(0, 1); c.finish()
    assert(c.project(row(0, dirty)).csrState(0x300) == 0x4000)
    c.validateFinal()
  }

  test("an FS dirty request without the actual register transition is rejected") {
    val c = new FpCommitState(64); c.allocate(1)
    clock(c, 0)
    assertThrows[IllegalArgumentException](clock(c, 0, dirty = Seq(1)))
  }

  test("a missing summary dirty bit is not repaired in the trace") {
    val c = new FpCommitState(64); c.allocate(1)
    clock(c, 0)
    assertThrows[IllegalArgumentException](clock(c, 0, status = 0x6000, dirty = Seq(1)))
  }

  test("reused hardware IDs retain different retirement generations") {
    val c = new FpCommitState(32); c.allocate(1)
    clock(c, 0)
    c.retire(0, 1)
    clock(c, 1, flags = Seq(1 -> BigInt(1)))
    clock(c, 1)
    c.allocate(1); c.retire(1, 1)
    clock(c, 0, csrs = Seq((1, 1, BigInt(0))))
    clock(c, 0)
    c.finish()
    assert(c.project(row(0)).fpState.get.flags == 1)
    assert(c.project(row(1)).fpState.get.flags == 0)
  }

  test("a state change from a micro-op that never retires cannot get trace credit") {
    val c = new FpCommitState(64); c.allocate(1)
    clock(c, 0)
    clock(c, 1, flags = Seq(1 -> BigInt(1)))
    clock(c, 1)
    assertThrows[IllegalArgumentException](c.finish())
  }

  test("unsettled state writes cannot get a projected result") {
    val c = new FpCommitState(64); c.allocate(1)
    clock(c, 0)
    c.retire(0, 1)
    assertThrows[IllegalArgumentException](c.finish(pending = true))
  }
}
