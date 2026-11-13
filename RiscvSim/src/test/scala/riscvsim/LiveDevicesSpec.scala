package riscvsim

import java.io.File
import org.scalatest.funsuite.AnyFunSuite

class LiveDevicesSpec extends AnyFunSuite {
  def fresh() = new LiveDevices(SimMap.load(new File("../examples/vexriscv/live-devices.json")))
  test("UART RX FIFO drives PLIC claim, completion and echo") {
    val d = fresh()
    d.write(0x10000002L, 1, 1)
    d.write(0x10000001L, 1, 1)
    d.write(0xc000004L, 4, 1)
    d.write(0xc002000L, 4, 2)
    assert(d.tick(2999) == 0)
    assert(d.tick(3000) == 0x800)
    assert(d.read(0xc200004L, 4) == 1)
    assert(d.tick(3001) == 0)
    for (b <- "echo\n") {
      assert((d.read(0x10000005L, 1) & 1) == 1)
      val received = d.read(0x10000000L, 1)
      assert(received == b.toInt)
      d.write(0x10000000L, 1, received)
    }
    d.write(0xc200004L, 4, 1)
    assert(d.tick(3002) == 0)
    assert(d.outputs("uart").str == "echo\n")
    assert(fresh().outputs("uart").str == "")
  }
  test("CLINT software and timer levels clear through MMIO") {
    val d = fresh()
    d.write(0x2000000L, 4, 1)
    d.write(0x2004000L, 4, 10)
    d.write(0x2004004L, 4, 0)
    assert(d.tick(99) == 8)
    assert(d.tick(100) == 0x88)
    d.write(0x2000000L, 4, 0)
    d.write(0x2004000L, 4, 20)
    assert(d.tick(101) == 0)
  }
  test("device access widths and missing claims refuse") {
    val d = fresh()
    intercept[IllegalArgumentException](d.read(0x10000000L, 4))
    intercept[IllegalArgumentException](d.write(0xc200004L, 4, 1))
    intercept[IllegalArgumentException](d.read(0x90000000L, 4))
  }
}
