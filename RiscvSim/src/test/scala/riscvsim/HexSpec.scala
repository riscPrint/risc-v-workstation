package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class HexSpec extends AnyFunSuite {
  test("signed trace PCs and CSR PCs compare at architectural width") {
    assert(Hex.signExtend(BigInt("ff800003b4", 16), 40, 64) == BigInt("ffffffff800003b4", 16))
    assert(Hex.signExtend(BigInt("800003b4", 16), 40, 64) == BigInt("800003b4", 16))
    assert(Hex.signExtend(BigInt("ffffffff800003b4", 16), 64, 64) == BigInt("ffffffff800003b4", 16))
  }
  test("canonicalization keeps distinct PCs distinct for trap freshness") {
    assert(Hex.signExtend(BigInt("ff800003b4", 16), 40, 64) != BigInt("ffffffff800003b8", 16))
  }
}
