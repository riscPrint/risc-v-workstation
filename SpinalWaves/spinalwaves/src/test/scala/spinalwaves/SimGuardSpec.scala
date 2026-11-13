package spinalwaves

import java.nio.file.{Files, Paths}
import org.scalatest.funsuite.AnyFunSuite
import spinal.core.sim._
import spinalwaves.examples.Gcd

class SimGuardSpec extends AnyFunSuite {
  test("a hung testbench stops at the sim timeout instead of growing the VCD forever") {
    val sim = SpinalWavesSim(SimConfig.workspacePath("target/simguard"), launchViewer = false, simTimeout = Some(2000))
      .compile(new Gcd)
    val e = intercept[Throwable] {
      sim.doSim("hang") { dut =>
        dut.clockDomain.forkStimulus(10)
        while (true) dut.clockDomain.waitSampling() // waits for an event that never comes
      }
    }
    assert(String.valueOf(e.getMessage).contains("Timeout"), e)
    val wave = SpinalCompat.waveFile(sim.compiled, "hang").toPath
    assert(Files.isRegularFile(wave) && Files.size(wave) < 1000000, s"VCD size ${Files.size(wave)}")
  }

  test("SPINAL_SIM_TIMEOUT parsing") {
    assert(SimGuard.defaultTimeout.isEmpty || SimGuard.defaultTimeout.exists(_ > 0))
  }
  test("a failed second run must not expose the first run's waveform") {
    val sim = SpinalWavesSim(SimConfig.workspacePath("target/simguard-stale"), launchViewer = false)
      .compile(new Gcd)
    sim.doSim("first", 42) { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(3)
    }
    assert(Files.isRegularFile(sim.vcdFile))
    intercept[Throwable] {
      sim.doSim("failed", 43) { _ => throw new IllegalStateException("injected failure") }
    }
    intercept[IllegalStateException](sim.vcdFile)
    intercept[IllegalStateException](sim.extraScopes)
    sim.doSim("third", 44) { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(3)
    }
    assert(sim.vcdFile.toString.contains("third"))
  }

}
