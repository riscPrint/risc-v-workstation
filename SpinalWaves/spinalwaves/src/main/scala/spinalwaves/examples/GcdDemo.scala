package spinalwaves.examples

import spinal.core.sim._
import spinalwaves.SpinalWavesSim

/** sbt 'runMain spinalwaves.examples.GcdDemo'; append --viewer to open Surfer. */
object GcdDemo {
  def main(args: Array[String]): Unit = {
    val compiled = SpinalWavesSim(SimConfig.workspacePath("target/examples"),
      launchViewer = args.contains("--viewer")).compile(new Gcd())
    compiled.doSim("gcd", 42) { dut =>
      dut.io.a #= 48
      dut.io.b #= 18
      dut.io.load #= false
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(3)
      dut.io.load #= true
      dut.clockDomain.waitSampling()
      dut.io.load #= false
      dut.clockDomain.waitSampling()
      var cycles = 0
      while (!dut.io.valid.toBoolean && cycles < 100) {
        dut.clockDomain.waitSampling()
        cycles += 1
      }
      assert(cycles < 100 && dut.io.result.toInt == 6)
    }
    println(s"VCD: ${compiled.vcdFile.toAbsolutePath}")
    println(s"HGLDD: ${compiled.hglddFile.toAbsolutePath}")
    println(s"Scopes: ${compiled.extraScopes.mkString(" ")}")
  }
}
