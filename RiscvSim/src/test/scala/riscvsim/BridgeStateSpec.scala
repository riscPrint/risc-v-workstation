package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class BridgeStateSpec extends AnyFunSuite {
  test("live bridge restores register and memory state without prefix execution") {
    val directory = Files.createTempDirectory("bridge-state").toFile
    val bridge = new BridgeState
    class Fixture extends Component {
      val io = new Bundle { val address = in UInt(2 bits); val data = in Bits(8 bits); val value = out Bits(8 bits); val synced = out Bits(8 bits) }
      val count = Reg(UInt(8 bits)) init 0
      count := count + 1
      val mem = Mem(Bits(8 bits), 4)
      mem.write(io.address, io.data)
      io.value := mem.readAsync(io.address)
      io.synced := mem.readSync(io.address, readUnderWrite = readFirst)
    }
    try {
      val compiled = SimConfig.withConfig(bridge.instrument(SpinalConfig()))
        .withVerilator.workspacePath(directory.getPath).compile(new Fixture)
      var state: ujson.Value = ujson.Null
      compiled.doSim { dut =>
        dut.io.address #= 0; dut.io.data #= 42
        dut.clockDomain.forkStimulus(10)
        dut.clockDomain.waitSampling(8); dut.clockDomain.waitFallingEdge(); sleep(1)
        state = ujson.read(ujson.write(bridge.capture()))
      }
      compiled.doSim { dut =>
        dut.clockDomain.clockSim #= false; dut.clockDomain.resetSim #= false
        dut.io.address #= 0; dut.io.data #= 0; sleep(1)
        bridge.restore(state); sleep(1)
        assert(bridge.capture() == state)
        assert(dut.io.value.toBigInt == 42)
        assert(dut.io.synced.toBigInt == 42)
        val broken = ujson.read(ujson.write(state)); broken("registers") = ujson.Arr()
        intercept[IllegalArgumentException](bridge.restore(broken))
        assert(bridge.capture() == state)
      }
    } finally org.apache.commons.io.FileUtils.deleteDirectory(directory)
  }
}
