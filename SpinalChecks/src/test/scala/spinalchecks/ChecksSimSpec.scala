package spinalchecks

import java.nio.file.{Files, Paths}

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._

class ChecksSimSpec extends AnyFunSuite {
  class Toggle extends Component {
    val breakProtocol = in Bool()
    val beat = master(Stream(Bits(8 bits)))
    val phase = RegInit(False)
    phase := !phase
    beat.valid := !breakProtocol || phase
    beat.payload := 0
  }

  for (mode <- Seq(Mode.Assert, Mode.Monitor, Mode.Both)) test(s"run reports in ${mode.name} mode") {
    val dir = s"generated/checks_sim_${mode.name}"
    val (cfg, result) = SpinalChecks.install(SpinalConfig(targetDirectory = dir,
      defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC)), ChecksConfig(mode = mode))
    val compiled = SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName(s"checks_sim_${mode.name}")
      .withVerilator.compile(new Toggle)
    for (broken <- Seq(false, true)) compiled.doSim(seed = 1) { dut =>
      dut.breakProtocol #= broken
      dut.beat.ready #= false
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(4)
      dut.clockDomain.waitFallingEdge()
      var previous = dut.beat.valid.toBoolean
      var drops = 0
      for (_ <- 0 until 8) {
        dut.clockDomain.waitFallingEdge()
        val valid = dut.beat.valid.toBoolean
        if (previous && !valid) drops += 1
        previous = valid
      }
      assert(drops == (if (broken) 4 else 0))
      assert(result.inserted.size == 2)
      val report = s"$dir/run_$broken.json"
      Files.deleteIfExists(Paths.get(report))
      if (mode == Mode.Assert) {
        assert(intercept[IllegalArgumentException](ChecksSim.firings(dut)).getMessage.contains("monitor"))
        intercept[IllegalArgumentException](ChecksSim.runReport(result, Nil, Seq("status" -> Json.Str("pass"))))
        intercept[IllegalArgumentException](ChecksSim.writeRunReport(dut, report))
        assert(!Files.exists(Paths.get(report)))
      } else {
        assert(result.inserted.forall(_.activationCount != null))
        assert(result.inserted.find(_.kind == Kind.StreamValidHold).get.activationCount.toLong > 0)
        if (!broken) assert(result.inserted.forall(_.activationCount.toLong > 0))
        else assert(result.inserted.find(_.kind == Kind.StreamPayloadStable).get.activationCount.toLong == 0)
        val fs = ChecksSim.firings(dut)
        assert(fs.map(_.check.id).toSet == (if (broken) Set("stream.valid_hold:beat") else Set.empty[String]))
        if (broken) assert(fs.head.count >= drops)
        ChecksSim.writeRunReport(dut, report, Seq("status" -> Json.Str("pass")))
        val text = new String(Files.readAllBytes(Paths.get(report)), "UTF-8")
        assert(text.contains("\"fired\": " + fs.size))
        assert(text.contains("\"status\": \"" + (if (broken) "fail" else "pass") + "\""))
      }
    }
  }
}
