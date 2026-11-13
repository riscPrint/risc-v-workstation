package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._

class StreamCancellationSpec extends AnyFunSuite {
  class Top(kind: String) extends Component {
    val cancel = in Bool()
    val value = in Bits(8 bits)
    val permit = in Bool()
    val source = Stream(Bits(8 bits))
    source.valid := True
    source.payload := value
    def m2sPipeWithFlush(input: Stream[Bits], flush: Bool): Stream[Bits] = {
      val result = Stream(Bits(8 bits))
      val valid = RegNextWhen(input.valid, input.ready).init(False)
      val data = RegNextWhen(input.payload, input.ready)
      valid.clearWhen(flush)
      input.ready := !result.valid || result.ready
      result.valid := valid
      result.payload := data
      result
    }
    val output = kind match {
      case "halt" => source.haltWhen(cancel)
      case "clear" => source.clearValidWhen(cancel)
      case "throw" => source.throwWhen(cancel)
      case "pipe" => source.m2sPipe(flush = cancel)
      case "throw-pipe" => source.m2sPipe(flush = cancel).throwWhen(False)
      case "custom" => m2sPipeWithFlush(source, cancel)
      case "and" =>
        val p = source.m2sPipe(flush = cancel)
        val s = Stream(Bits(8 bits))
        s.valid := p.valid && permit
        s.payload := p.payload
        p.ready := s.ready
        s
      case "unknown" | "declared" =>
        val s = Stream(Bits(8 bits))
        s.valid := !cancel
        s.payload := value
        source.ready := s.ready
        s
    }
    output.ready := False
    val observed = out Bits(8 bits)
    observed := output.payload
  }

  for (kind <- Seq("halt", "clear", "throw", "pipe", "custom", "and", "throw-pipe", "unknown", "declared")) {
    test(s"$kind: legal cancellation and illegal payload mutation") {
      val base = SpinalConfig(targetDirectory = s"generated/cancel-$kind",
        debugComponents = scala.collection.mutable.HashSet[Class[_]](classOf[Top]),
        defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC))
      val (cfg, checks) = SpinalChecks.install(base, ChecksConfig(mode = Mode.Monitor,
        streamCancellations = if (kind == "declared")
          Seq(StreamCancelBinding("output", "cancel", false, "reviewed combinational clear")) else Nil))
      val sim = SimConfig.withConfig(cfg).workspacePath("simWorkspace")
        .workspaceName(s"cancel_$kind").withVerilator.compile(new Top(kind))
      for (illegal <- Seq(false, true)) sim.doSim(seed = 17) { d =>
        d.cancel #= false; d.value #= 3; d.permit #= true
        d.clockDomain.forkStimulus(10)
        d.clockDomain.waitSampling(8)
        d.clockDomain.waitFallingEdge()
        if (illegal) d.value #= 7 else d.cancel #= true
        d.clockDomain.waitSampling()
        d.clockDomain.waitFallingEdge()
        d.cancel #= false
        d.clockDomain.waitSampling(4)
        val ids = ChecksSim.firings(d).map(_.check.id).toSet
        if (illegal) assert(ids.exists(_.startsWith("stream.payload_stable:")), ids)
        else if (!illegal && kind == "unknown") assert(ids.exists(_.startsWith("stream.valid_hold:")), ids)
        else assert(ids.isEmpty, ids)
      }
      val recognized = checks.records.filter(r => r.detail.startsWith("cancellation-aware:"))
      assert(recognized.nonEmpty == (kind != "unknown"), checks.records.map(r => r.id + " " + r.detail))
    }
  }
  for (bindings <- Seq(
    Seq(StreamCancelBinding("absent", "cancel", false, "test")),
    Seq(StreamCancelBinding("output", "absent", false, "test")),
    Seq.fill(2)(StreamCancelBinding("output", "cancel", false, "test")))) {
    test(s"invalid cancellation binding fails elaboration: $bindings") {
      val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/cancel-invalid"),
        ChecksConfig(streamCancellations = bindings))
      intercept[Exception] { cfg.generateVerilog(new Top("unknown")) }
    }
  }

}
