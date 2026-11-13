package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class ByteMemorySpec extends AnyFunSuite {
  test("RAM preserves byte values and checks both boundaries") {
    val ram = new ByteMemory(0x80000000L, 16)
    assert(ram.getOrElse(0x80000000L, -1) == 0)
    ram(0x80000000L) = 0x80
    ram(0x8000000fL) = 0xff
    assert(ram.getOrElse(0x80000000L, -1) == 0x80)
    assert(ram.getOrElse(0x8000000fL, -1) == 0xff)
    assert(ram.getOrElse(0x7fffffffL, -1) == -1)
    assert(ram.getOrElse(0x80000010L, -1) == -1)
    intercept[IllegalArgumentException](ram(0x80000010L) = 1)
    intercept[IllegalArgumentException](ram(0x7fffffffL) = 1)
    intercept[IllegalArgumentException](new ByteMemory(Long.MaxValue, 2))
  }
}
