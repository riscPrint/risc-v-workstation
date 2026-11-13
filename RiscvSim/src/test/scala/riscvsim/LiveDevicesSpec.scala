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
  test("snapshot resumes pending UART, claimed PLIC and timer state") {
    val d = fresh()
    d.write(0x10000002L, 1, 1); d.write(0x10000001L, 1, 1)
    d.write(0xc000004L, 4, 1); d.write(0xc002000L, 4, 2)
    d.write(0x2004000L, 4, 301); d.write(0x2004004L, 4, 0)
    assert(d.tick(3000) == 0x800)
    assert(d.read(0xc200004L, 4) == 1)
    val saved = d.snapshot()
    val restored = fresh(); restored.restore(saved)
    assert(restored.snapshot() == saved)
    for (device <- Seq(d, restored)) {
      assert(device.tick(3001) == 0)
      device.write(0xc200004L, 4, 1)
      assert(device.tick(3010) == 0x880)
      assert(device.read(0x10000000L, 1) == 'e'.toInt)
    }
    assert(restored.snapshot() == d.snapshot())
    intercept[IllegalArgumentException](fresh().restore(ujson.Obj("schema" -> "bad")))
  }
  test("device-wide reset clears FIFO, output, deadlines and claimed gateways") {
    val d = fresh()
    val initial = d.snapshot()
    d.write(0x10000001L, 1, 1)
    d.write(0xc000004L, 4, 7); d.write(0xc002000L, 4, 2)
    assert(d.tick(3000) == 0x800)
    assert(d.read(0xc200004L, 4) == 1)
    d.write(0x10000002L, 1, 1)
    d.write(0x10000007L, 1, 99)
    d.write(0x10000000L, 1, 80)
    d.write(0x2000000L, 4, 1)
    d.write(0x2004000L, 4, 0); d.write(0x2004004L, 4, 0)
    assert(d.snapshot() != initial)
    d.reset()
    assert(d.snapshot() == initial)
    assert(d.outputs("uart").str == "")
    assert(d.tick(2999) == 0)
    assert(d.read(0xc200004L, 4) == 0)
  }
  test("UART firmware modem control survives snapshots and resets") {
    val d = fresh()
    d.write(0x10000004L, 1, 3)
    val state = d.snapshot()
    assert(d.read(0x10000004L, 1) == 3)
    d.reset()
    assert(d.read(0x10000004L, 1) == 0)
    d.restore(state)
    assert(d.read(0x10000004L, 1) == 3)
    intercept[IllegalArgumentException](d.write(0x10000004L, 1, 32))
  }

  test("CLINT RV64 accesses preserve both halves and reject other wide registers") {
    val d = fresh()
    val value = (BigInt(1) << 32) + 5
    d.write(0x2004000L, 8, value)
    assert(d.read(0x2004000L, 8) == value)
    assert(d.read(0x2004000L, 4) == 5)
    assert(d.read(0x2004004L, 4) == 1)
    d.tick(100)
    assert(d.read(0x200bff8L, 8) == 10)
    d.write(0x2004000L, 8, 3)
    assert(d.tick(100).testBit(7))
    d.reset()
    assert(d.read(0x2004000L, 8) == (BigInt(1) << 64) - 1)
    intercept[IllegalArgumentException](d.read(0x2000000L, 8))
    intercept[IllegalArgumentException](d.write(0xc002000L, 8, 0))
  }

  test("UART supports Linux FIFO and loopback discovery") {
    val d = fresh()
    d.write(0x10000001L, 1, 15)
    assert(d.read(0x10000001L, 1) == 15)
    d.write(0x10000001L, 1, 0)
    d.write(0x10000002L, 1, 0xc7)
    assert(d.read(0x10000002L, 1) == 0xc1)
    d.write(0x10000004L, 1, 0x1a)
    assert((d.read(0x10000006L, 1) & 0xf0) == 0x90)
    d.write(0x10000000L, 1, 0x55)
    assert(d.read(0x10000000L, 1) == 0x55)
    assert(d.outputs("uart").str == "")
    d.write(0x10000004L, 1, 0)
    assert((d.read(0x10000006L, 1) & 0xf0) == 0xb0)
    val snapshot = d.snapshot(); val restored = fresh(); restored.restore(snapshot)
    assert(restored.snapshot() == snapshot)
  }
  test("power-off device stops only on the configured command and restores state") {
    val path = java.nio.file.Files.createTempFile("poweroff-map", ".json")
    try {
      val map = ujson.read(java.nio.file.Files.readString(new File("../examples/vexriscv/live-devices.json").toPath))
      map("regions").arr += ujson.Obj("name" -> "poweroff", "kind" -> "mmio", "base" -> "0x100000", "size" -> "0x1000",
        "permissions" -> "rw", "cacheable" -> false, "registers" -> ujson.Arr())
      map("devices").arr += ujson.Obj("region" -> "poweroff", "model" -> "syscon-poweroff", "value" -> "0x5555")
      java.nio.file.Files.writeString(path, ujson.write(map))
      val d = new LiveDevices(SimMap.load(path.toFile))
      d.write(0x100000, 4, 0); assert(!d.poweroff)
      d.write(0x100000, 4, 0x5555); assert(d.poweroff)
      val restored = new LiveDevices(SimMap.load(path.toFile)); restored.restore(d.snapshot())
      assert(restored.poweroff)
      restored.reset(); assert(!restored.poweroff)
    } finally java.nio.file.Files.delete(path)
  }

  test("PLIC threshold masks notification but does not mask claim polling") {
    val d = fresh()
    d.write(0x10000001L, 1, 1)
    d.write(0xc000004L, 4, 1)
    d.write(0xc002000L, 4, 2)
    d.write(0xc200000L, 4, 7)
    assert(d.tick(3000) == 0)
    assert(d.read(0xc001000L, 4) == 2)
    assert(d.read(0xc200004L, 4) == 1)
    assert(d.read(0xc200004L, 4) == 0)
    d.write(0xc200004L, 4, 1)
    assert(d.tick(3001) == 0)
    assert(d.read(0xc200004L, 4) == 1)
  }

  test("PLIC pending request survives source deassertion until claim") {
    val d = fresh()
    d.write(0x10000002L, 1, 1)
    d.write(0x10000001L, 1, 1)
    d.write(0xc000004L, 4, 1)
    d.write(0xc002000L, 4, 2)
    assert(d.tick(3000) == 0x800)
    for (_ <- 0 until 5) d.read(0x10000000L, 1)
    assert(d.tick(3001) == 0x800)
    val saved = d.snapshot()
    val restored = fresh(); restored.restore(saved)
    for (device <- Seq(d, restored)) {
      assert(device.read(0xc200004L, 4) == 1)
      device.write(0xc200004L, 4, 1)
      assert(device.tick(3002) == 0)
    }
    assert(d.snapshot() == restored.snapshot())
  }

  test("UART IIR read acknowledges a pending THRE interrupt") {
    val d = fresh()
    d.write(0x10000001L, 1, 2)
    assert(d.read(0x10000002L, 1) == 2)
    assert(d.read(0x10000002L, 1) == 1)
    d.write(0x10000000L, 1, 65)
    assert(d.read(0x10000002L, 1) == 2)
    val saved = d.snapshot()
    val restored = fresh(); restored.restore(saved)
    assert(restored.read(0x10000002L, 1) == 1)
  }

}
