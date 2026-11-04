package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.lib.bus.tilelink._
import spinal.lib.bus.tilelink.sim._
import spinalchecks.sim.TileLinkMemoryScoreboard

class MemoryScoreboardSpec extends AnyFunSuite {
  def request(source: Int, put: Boolean = false): TransactionA = {
    val a = TransactionA(); a.source = source; a.address = 0; a.size = 2
    a.opcode = if (put) Opcode.A.PUT_PARTIAL_DATA else Opcode.A.GET
    a.data = Array[Byte](9, 8, 7, 6); a.mask = Array(true, false, true, false)
    a
  }
  def response(source: Int, data: Array[Byte], denied: Boolean = false): TransactionD = {
    val d = new TransactionD(); d.source = source; d.size = 2; d.denied = denied
    d.opcode = if (data == null) Opcode.D.ACCESS_ACK else Opcode.D.ACCESS_ACK_DATA
    d.data = data; d
  }
  def model = new TileLinkMemoryScoreboard((0 until 4).map(i => BigInt(i) -> i.toByte).toMap)
  test("masked writes affect reads and independent responses can reorder") {
    val m = model
    m.onA(request(0, true)); m.onD(response(0, null))
    m.onA(request(1)); m.onA(request(2))
    m.onD(response(2, Array[Byte](9, 1, 7, 3))); m.onD(response(1, Array[Byte](9, 1, 7, 3)))
    m.assertComplete()
  }
  test("injected bad data and unexpected response errors fail") {
    val m = model; m.onA(request(0))
    intercept[IllegalArgumentException](m.onD(response(0, Array[Byte](0, 1, 2, 9))))
    intercept[IllegalArgumentException](m.onD(response(0, Array[Byte](0, 1, 2, 3), denied = true)))
  }
  test("declared denial and outstanding or empty runs remain explicit") {
    val m = model
    intercept[IllegalArgumentException](m.assertComplete())
    m.expectDenied(0); m.onA(request(0))
    intercept[IllegalArgumentException](m.assertComplete())
    m.onD(response(0, Array[Byte](0, 1, 2, 3), denied = true)); m.assertComplete()
  }
}
