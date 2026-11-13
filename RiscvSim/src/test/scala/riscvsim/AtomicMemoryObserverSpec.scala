package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class AtomicMemoryObserverSpec extends AnyFunSuite {
  def observer = new AtomicMemoryObserver(Seq.fill[Byte](32)(0), Set(0, 1, 2), 16, 2, "certified loop; fair port")
  test("remote writes invalidate the configured reservation set and failed SC cannot write") {
    val m = observer
    m.loadReserved(0, 0, 0, 8, 0)
    m.store(1, 1, 8, 8, 7, 7)
    intercept[IllegalArgumentException](m.storeConditional(2, 0, 0, 8, 9, true, 9, true))
    m.storeConditional(2, 0, 0, 8, 9, false, 0, true)
    assert(m.bytes(0, 1) == Vector[Byte](0))
  }
  test("bounded spurious failures require a declared constrained-loop service condition") {
    val m = observer
    for (i <- 0 until 2) {
      m.loadReserved(i*2, 0, 0, 8, 0)
      m.storeConditional(i*2+1, 0, 0, 8, 1, false, 0, true)
    }
    m.loadReserved(4, 0, 0, 8, 0)
    intercept[IllegalArgumentException](m.storeConditional(5, 0, 0, 8, 1, false, 0, true))
    m.storeConditional(5, 0, 0, 8, 1, true, 1, true)
  }
  test("RV64 concurrent AMOs reject torn data and stale old values") {
    val m = observer
    m.amo(0, 0, 0, 8, "swap", BigInt("ffffffff00000000", 16), 0, BigInt("ffffffff00000000", 16))
    intercept[IllegalArgumentException](m.amo(1, 1, 0, 8, "add", 1, 0, 1))
    intercept[IllegalArgumentException](m.amo(1, 1, 0, 8, "add", 1, BigInt("ffffffff00000000", 16), 1))
    m.amo(1, 1, 0, 8, "add", 1, BigInt("ffffffff00000000", 16), BigInt("ffffffff00000001", 16))
    m.amo(2, 2, 0, 8, "max", 1, BigInt("ffffffff00000001", 16), 1)
    assert(m.bytes(8, 8) == Vector.fill[Byte](8)(0))
  }
  test("CAS checks quadword success, failure and adjacent bytes") {
    val m = observer
    val wide = BigInt(1) << 120
    m.compareSwap(0, 0, 0, 16, 0, wide, 0, wide)
    intercept[IllegalArgumentException](m.compareSwap(1, 1, 0, 16, 0, 9, wide, 9))
    m.compareSwap(1, 1, 0, 16, 0, 9, wide, wide)
    m.compareSwap(2, 2, 0, 16, wide, 9, wide, 9)
    assert(m.bytes(16, 16) == Vector.fill[Byte](16)(0))
  }
}
