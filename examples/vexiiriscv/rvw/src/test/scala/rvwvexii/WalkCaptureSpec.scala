package rvwvexii

import org.scalatest.funsuite.AnyFunSuite

class WalkCaptureSpec extends AnyFunSuite {
  test("an Sv32 walk becomes one ordered mmu_walk record") {
    val c = new WalkCapture(32, 32)
    c.start(BigInt(0x40000000L), read = true, write = false, execute = false, rootPpn = BigInt(0x80010))
    c.command(BigInt(0x80010400L))
    c.response(BigInt(0x20004401L), error = false)
    c.command(BigInt(0x80011000L))
    c.response(BigInt(0x200800cfL), error = false)
    c.done(20, pageFault = false, accessFault = false, address = BigInt(0x80200000L))
    assert(c.due(19).isEmpty)
    val Seq(r) = c.due(20)
    assert(r("mode").str == "sv32" && r("access").str == "load" && r("access_id").num == 0)
    assert(r("root").str == "0x80010000" && r("va").str == "0x40000000" && r("pa").str == "0x80200000")
    assert(r("reads").arr.map(_("level").num.toInt) == Seq(1, 0))
    assert(r("reads")(1)("data").str == "0x200800cf")
    assert(c.undelivered == 0 && c.walks == 1)
  }

  test("faults keep the status and omit data for an erroring read") {
    val c = new WalkCapture(64, 39)
    c.start(BigInt(1) << 38, read = true, write = true, execute = false, rootPpn = BigInt(0x80010))
    c.command(BigInt(0x80010000L))
    c.response(BigInt(0), error = true)
    c.done(9, pageFault = false, accessFault = true, address = BigInt(0x80010000L))
    val Seq(r) = c.due(9)
    assert(r("va").str == "0xffffffc000000000" && r("access").str == "store")
    assert(r("status").str == "access-fault" && !r.value.contains("pa"))
    assert(r("reads")(0)("fault").bool && !r("reads")(0).obj.contains("data"))
  }

  test("a response without a read is refused") {
    val c = new WalkCapture(32, 32)
    intercept[IllegalStateException](c.response(BigInt(0), error = false))
  }
}
