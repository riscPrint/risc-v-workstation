package spinaltrace

import java.io.File

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinaltrace.SpinalTraceSim.expect
import spinaltrace.TraceTestKit._
import spinaltrace.examples._

/** End-to-end: simulate each example with Verilator, extract pdg.json, run the CLI dynamic trace on a
  * criterion at a chosen time and check the source lines / dependency kinds that must (and must not)
  * appear. */
class ExamplesTraceSpec extends AnyFunSuite {
  private val sim  = SimConfig.workspacePath(simWorkspace)
  private val opts = SpinalTraceSimOptions(extract = ExtractOptions(sourceRoots = Seq(new File(repo, "examples/src"))),
    onFailure = OnFailure.RunCli, cliPath = cli)
  private def compile[T <: Component](gen: => T): TracedSim[T] = SpinalTraceSim.compile(sim, opts)(gen)

  private val gcdFile = "Gcd.scala"
  private val ft      = "Features.scala"

  private def gcdBench(dut: GCD, expected: Int): Long = {
    dut.clockDomain.forkStimulus(10)
    dut.io.a #= 24
    dut.io.b #= 36
    dut.io.loadValues #= true
    dut.clockDomain.waitSampling()
    dut.io.loadValues #= false
    var cycles = 0
    while (!dut.io.resultIsValid.toBoolean && cycles < 10) { dut.clockDomain.waitSampling(); cycles += 1 }
    expect(dut.io.resultIsValid, true)
    expect(dut.io.result, expected)
    simTime()
  }

  test("GCD (ChiselTrace README example): trace io.result back to the load and the subtractions") {
    val t = compile(new GCD)
    var checkedAt = 0L
    t.doSim("gcd")(dut => checkedAt = gcdBench(dut, 12))
    val d = trace(t.pdg, waveOf(t, "gcd"), "signal:io.result", Seq("--at-time", SpinalTraceSim.traceTime(checkedAt).toString))

    val resultLine = lineOf(gcdFile, "io.result        := x")
    val subX       = lineOf(gcdFile, "x := x - y")
    val subY       = lineOf(gcdFile, "y := y - x")
    val cond       = lineOf(gcdFile, "when(x > y)")
    val loadX      = lineOf(gcdFile, "x := io.a")
    val loadY      = lineOf(gcdFile, "y := io.b")
    val loadCond   = lineOf(gcdFile, "when(io.loadValues)")
    val lines      = d.lines(gcdFile)
    Seq(resultLine, subX, subY, cond, loadX, loadY, loadCond).foreach(l => assert(lines.contains(l), s"line $l missing:\n$d"))
    // spurious: the unused tmp and the valid flag do not influence io.result
    assert(!lines.contains(lineOf(gcdFile, "val tmp = x + y")), d)
    assert(!lines.contains(lineOf(gcdFile, "io.resultIsValid := y === 0")), d)
    // the criterion node is io.result, valued 12
    val top = d.at(gcdFile, resultLine).maxBy(_.timestamp)
    assert(top.simData.exists(_.startsWith("12")), d)
    assert(d.has(onLine(gcdFile, resultLine), onLine(gcdFile, subX), "Data"), d)
    assert(d.has(onLine(gcdFile, subX), onLine(gcdFile, cond), "Conditional"), d)
    assert(d.has(onLine(gcdFile, loadX), onLine(gcdFile, loadCond), "Conditional"), d)
    assert(d.has(onLine(gcdFile, loadX), withName("input_io_a"), "Data"), d)
    assert(!d.kinds.contains("Index"), d)
  }

  test("GCD expecting 13 (README): the debugger prepares and runs a trace of io_result") {
    val t = compile(new GCD)
    val e = intercept[SpinalTraceFailure](t.doSim("gcd13")(dut => gcdBench(dut, 13)))
    assert(e.cause.isInstanceOf[ExpectationFailed])
    val s = e.session.getOrElse(fail("no trace session"))
    assert(s.criterion == "signal:io_result")
    assert(s.cliCommand().contains("--at-time"))
    assert(s.guiCommand().head == opts.guiPath)
    assert(s.output.isFile, "the CLI should have written dynpdg.json")
    val d = parse(ujson.read(scala.io.Source.fromFile(s.output).mkString), e.cliOutput.getOrElse(""))
    assert(d.lines(gcdFile).contains(lineOf(gcdFile, "x := x - y")), d)
  }

  test("injected bug: the trace of the wrong GCD result reaches the faulty line") {
    val t = compile(new BuggyGCD)
    val e = intercept[SpinalTraceFailure] {
      t.doSim("buggy") { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.io.a #= 24; dut.io.b #= 36; dut.io.loadValues #= true
        dut.clockDomain.waitSampling()
        dut.io.loadValues #= false
        dut.clockDomain.waitSampling(6)
        expect(dut.io.result, 12)
      }
    }
    val s = e.session.get
    val d = parse(ujson.read(scala.io.Source.fromFile(s.output).mkString), e.cliOutput.getOrElse(""))
    val faulty = lineOf(gcdFile, "x := x - y - 1 // BUG")
    val result = lineOf(gcdFile, "io.result        := x", after = "class BuggyGCD")
    assert(d.lines(gcdFile).contains(faulty), d)
    assert(d.has(onLine(gcdFile, result), onLine(gcdFile, faulty), "Data"), d)
  }

  test("when / elsewhen / otherwise: only the taken branch and its condition chain appear") {
    val t = compile(new WhenChain)
    var at = 0L
    t.doSim("chain") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.a #= 1; dut.io.b #= 2; dut.io.c #= 3; dut.io.d #= 4
      dut.io.sel #= 0
      dut.clockDomain.waitSampling(2)
      dut.io.sel #= 2
      dut.clockDomain.waitSampling(2)
      at = simTime()
      expect(dut.io.result, 3)
      dut.clockDomain.waitSampling() // keep the inputs stable for the whole traced cycle
      dut.io.sel #= 3
      dut.clockDomain.waitSampling(2)
    }
    val d = trace(t.pdg, waveOf(t, "chain"), "signal:io_result", Seq("--at-time", SpinalTraceSim.traceTime(at).toString))
    val lines = d.lines(ft)
    val c2    = lineOf(ft, "picked := io.c")
    Seq(lineOf(ft, "io.result := picked"), c2, lineOf(ft, "when(io.sel === 0)"), lineOf(ft, "elsewhen (io.sel === 1)"),
      lineOf(ft, "elsewhen (io.sel === 2)")).foreach(l => assert(lines.contains(l), s"$l\n$d"))
    Seq(lineOf(ft, "picked := io.a"), lineOf(ft, "picked := io.b"), lineOf(ft, "picked := io.d")).foreach(l =>
      assert(!lines.contains(l), s"spurious line $l\n$d"))
    assert(d.has(onLine(ft, c2), onLine(ft, lineOf(ft, "elsewhen (io.sel === 2)")), "Conditional"), d)
    assert(d.has(onLine(ft, lineOf(ft, "elsewhen (io.sel === 2)")), onLine(ft, lineOf(ft, "elsewhen (io.sel === 1)")), "Conditional"), d)
    assert(d.has(onLine(ft, c2), withName("input_io_c"), "Data"), d)
    assert(!d.kinds.contains("Index"), d)
  }

  test("switch on a SpinalEnum with default: the matching is() and the default are told apart") {
    val t = compile(new SwitchEnum)
    var atSub, atDefault = 0L
    t.doSim("switch") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.a #= 9; dut.io.b #= 4
      dut.io.op #= AluOp.ADD
      dut.clockDomain.waitSampling(2)
      dut.io.op #= AluOp.SUB
      dut.clockDomain.waitSampling(2)
      atSub = simTime()
      expect(dut.io.result, 5)
      dut.clockDomain.waitSampling()
      dut.io.op #= AluOp.PASS
      dut.clockDomain.waitSampling(2)
      atDefault = simTime()
      expect(dut.io.result, 9)
    }
    val add = lineOf(ft, "acc := io.a + io.b")
    val sub = lineOf(ft, "acc := io.a - io.b")
    val defaultLine = scala.io.Source.fromFile(new File(examplesDir, ft)).getLines().toVector.indexWhere(_.trim == "acc := io.a") + 1
    val sw  = lineOf(ft, "switch(io.op)")

    val d1 = trace(t.pdg, waveOf(t, "switch"), "signal:io_result", Seq("--at-time", SpinalTraceSim.traceTime(atSub).toString))
    assert(d1.lines(ft).contains(sub), d1)
    assert(d1.lines(ft).contains(sw), d1)
    assert(!d1.lines(ft).contains(add) && !d1.lines(ft).contains(defaultLine), d1)
    assert(d1.has(onLine(ft, sub), onLine(ft, sw), "Conditional"), d1)
    // the static PDG has one case vertex per is() plus the default
    val names = PdgFile.statementNames(t.pdg)
    assert(names.exists(n => n.startsWith("case_on_[io_op is SUB")) && names.exists(n => n.startsWith("case_on_[io_op is ADD")), names)
    assert(names.exists(_ == "case_on_[io_op default]"), names)

    val d2 = trace(t.pdg, waveOf(t, "switch"), "signal:io_result", Seq("--at-time", SpinalTraceSim.traceTime(atDefault).toString))
    assert(d2.lines(ft).contains(defaultLine), d2)
    assert(!d2.lines(ft).contains(add) && !d2.lines(ft).contains(sub), d2)
    assert(d2.has(onLine(ft, defaultLine), onLine(ft, sw), "Conditional"), d2)
  }

  test("Vec with dynamic write and read index: Index edges to both indexes, only the right write") {
    val t = compile(new VecDynamic)
    var writeTime, at = 0L
    t.doSim("vec") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.wrEn #= false; dut.io.wrIdx #= 0; dut.io.wrData #= 0; dut.io.rdIdx #= 0
      dut.clockDomain.waitSampling(2)
      dut.io.wrEn #= true; dut.io.wrIdx #= 2; dut.io.wrData #= 0x55
      writeTime = simTime()
      dut.clockDomain.waitSampling()
      dut.io.wrIdx #= 1; dut.io.wrData #= 0x11
      dut.clockDomain.waitSampling()
      dut.io.wrEn #= false; dut.io.rdIdx #= 2
      dut.clockDomain.waitSampling(2)
      at = simTime()
      expect(dut.io.rdData, 0x55)
    }
    val d = trace(t.pdg, waveOf(t, "vec"), "signal:io_rdData", Seq("--at-time", SpinalTraceSim.traceTime(at).toString))
    val rd = lineOf(ft, "io.rdData := regs(io.rdIdx)")
    val wr = lineOf(ft, "regs(io.wrIdx) := io.wrData")
    assert(d.lines(ft).contains(rd) && d.lines(ft).contains(wr), d)
    assert(d.has(onLine(ft, rd), withName("input_io_rdIdx"), "Index"), d)
    assert(d.has(onLine(ft, wr), withName("input_io_wrIdx"), "Index"), d)
    assert(d.has(onLine(ft, wr), withName("input_io_wrData"), "Data"), d)
    // only the write of 0x55 (to element 2) is a dependency, not the later write of 0x11 to element 1
    val writes = d.at(ft, wr)
    assert(writes.size == 1 && writes.head.simData.exists(_.startsWith("85")), d)
    assert(!d.lines(ft).contains(lineOf(ft, "Vec.fill(4)(Reg(UInt(8 bits)) init (0))")), d)
  }

  test("Mux: select is an Index dependency, only the selected input is a Data dependency") {
    val t = compile(new MuxExample)
    var at = 0L
    t.doSim("mux") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.sel #= true; dut.io.a #= 5; dut.io.b #= 9; dut.io.c #= 0
      dut.clockDomain.waitSampling(2)
      at = simTime()
      expect(dut.io.picked, 5)
      expect(dut.io.maxOfAB, 9)
    }
    val p = trace(t.pdg, waveOf(t, "mux"), "signal:io_picked", Seq("--at-time", SpinalTraceSim.traceTime(at).toString))
    val pl = lineOf(ft, "io.picked  := Mux(io.sel, io.a, io.b)")
    assert(p.has(onLine(ft, pl), withName("input_io_a"), "Data"), p)
    assert(p.has(onLine(ft, pl), withName("input_io_sel"), "Index"), p)
    assert(!p.has(onLine(ft, pl), withName("input_io_b"), "Data"), p)

    val m = trace(t.pdg, waveOf(t, "mux"), "signal:io_maxOfAB", Seq("--at-time", SpinalTraceSim.traceTime(at).toString))
    val ml = lineOf(ft, "io.maxOfAB := Mux(io.a > io.b, io.a, io.b)")
    assert(m.has(onLine(ft, ml), withName("input_io_b"), "Data"), m)
    assert(!m.has(onLine(ft, ml), withName("input_io_a"), "Data"), m)
    assert(m.has(onLine(ft, ml), withName("input_io_a"), "Index"), m) // through the (named) a > b select
  }

  test("two-level hierarchy: the bug in the leaf is found from the toplevel output") {
    val t = compile(new HierTop)
    val e = intercept[SpinalTraceFailure] {
      t.doSim("hier") { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.io.a #= 10
        dut.clockDomain.waitSampling(3)
        expect(dut.io.result, 24) // (10 + 2) << 1 by specification
      }
    }
    val s = e.session.get
    assert(s.criterion == "signal:io_result")
    val d = parse(ujson.read(scala.io.Source.fromFile(s.output).mkString), e.cliOutput.getOrElse(""))
    val leaf = lineOf(ft, "io.y := io.x + 3 // BUG")
    val bug  = d.at(ft, leaf)
    assert(bug.nonEmpty, d)
    assert(bug.forall(_.modulePath == Seq("mid", "leaf")), d)
    Seq(lineOf(ft, "io.result := mid.io.y |<< 1"), lineOf(ft, "stage := leaf.io.y"), lineOf(ft, "leaf.io.x := io.x"),
      lineOf(ft, "mid.io.x  := io.a")).foreach(l => assert(d.lines(ft).contains(l), s"$l\n$d"))
    assert(d.has(onLine(ft, leaf), onLine(ft, lineOf(ft, "leaf.io.x := io.x")), "Data"), d)
  }

  test("register with init and a reset pulse mid-simulation: the trace restarts at the init value") {
    val t = compile(new ResetCounter)
    var beforeReset, afterReset = 0L
    var countAfter = 0
    t.doSim("reset") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.enable #= true
      dut.clockDomain.waitSampling(6)
      beforeReset = simTime()
      dut.clockDomain.assertReset()
      dut.clockDomain.waitRisingEdge(2) // waitSampling() would wait for the reset to be released
      dut.clockDomain.deassertReset()
      dut.clockDomain.waitSampling(3)
      afterReset = simTime()
      countAfter = dut.io.count.toInt
      dut.clockDomain.waitSampling()
    }
    val init = lineOf(ft, "Reg(UInt(8 bits)) init (5)")
    val inc  = lineOf(ft, "counter := counter + 1")
    val d = trace(t.pdg, waveOf(t, "reset"), "signal:io_count", Seq("--at-time", SpinalTraceSim.traceTime(afterReset).toString))
    assert(countAfter > 5 && countAfter < 10, s"count after the reset pulse: $countAfter")
    val top = d.at(ft, lineOf(ft, "io.count := counter")).maxBy(_.timestamp)
    assert(top.simData.exists(_.startsWith(countAfter.toString)), d)
    val incs  = d.at(ft, inc).map(_.timestamp)
    val inits = d.at(ft, init).map(_.timestamp)
    assert(incs.size == countAfter - 5, s"one increment per cycle since the reset expected\n$d")
    assert(inits.size == 1 && inits.head > 3, s"the init node must be the mid-simulation reset, not t=0\n$d")
    assert(incs.forall(_ > inits.head), d)

    val b = trace(t.pdg, waveOf(t, "reset"), "signal:io_count", Seq("--at-time", SpinalTraceSim.traceTime(beforeReset).toString))
    assert(b.at(ft, init).forall(_.timestamp <= 0), b)
    assert(b.at(ft, inc).size >= 5, b)
  }

  test("sync-read Mem: the read depends on the write of that address, one cycle late, with Index edges") {
    val t = compile(new SyncMem)
    var at = 0L
    t.doSim("mem") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.wrEn #= false; dut.io.wrAddr #= 0; dut.io.wrData #= 0; dut.io.rdAddr #= 0
      dut.clockDomain.waitSampling(2)
      dut.io.wrEn #= true; dut.io.wrAddr #= 3; dut.io.wrData #= 0x42
      dut.clockDomain.waitSampling()
      dut.io.wrAddr #= 5; dut.io.wrData #= 0x99
      dut.clockDomain.waitSampling()
      dut.io.wrEn #= false; dut.io.rdAddr #= 3
      dut.clockDomain.waitSampling(2)
      at = simTime()
      expect(dut.io.rdData, 0x42)
    }
    val d  = trace(t.pdg, waveOf(t, "mem"), "signal:io_rdData", Seq("--at-time", SpinalTraceSim.traceTime(at).toString))
    val rd = lineOf(ft, "io.rdData := mem.readSync(io.rdAddr)")
    val wr = lineOf(ft, "mem.write(io.wrAddr, io.wrData)")
    assert(d.lines(ft).contains(rd) && d.lines(ft).contains(wr), d)
    assert(d.has(onLine(ft, rd), withName("input_io_rdAddr"), "Index"), d)
    assert(d.has(onLine(ft, rd), onLine(ft, wr), "Data"), d)
    assert(d.has(onLine(ft, wr), withName("input_io_wrData"), "Data"), d)
    assert(d.has(onLine(ft, wr), withName("input_io_wrAddr"), "Index"), d)
    val writes = d.at(ft, wr)
    assert(writes.size == 1, s"only the write to address 3\n$d")
  }

  test("failing HDL assert: the debugger traces the assert statement") {
    val t = compile(new AssertCounter)
    val e = intercept[SpinalTraceFailure] {
      t.doSim("assert") { dut =>
        dut.clockDomain.forkStimulus(10)
        dut.clockDomain.waitSampling(30)
      }
    }
    val s = e.session.getOrElse(fail("no session"))
    assert(s.criterion.startsWith("statement:assert_Features_l"))
    val d = parse(ujson.read(scala.io.Source.fromFile(s.output).mkString), e.cliOutput.getOrElse(""))
    assert(d.lines(ft).contains(lineOf(ft, "counter := counter + 1", after = "class AssertCounter")), d)
    assert(d.lines(ft).contains(lineOf(ft, "Reg(UInt(4 bits)) init (0)")), d) // the chain reaches the reset value
    assert(d.lines(ft).contains(lineOf(ft, "assert(counter =/= 11")), d)
  }

  test("partial assignments: dynamic bit writes accumulate, fixed bits are separate providers") {
    val t = compile(new BitFlags)
    var afterSets, afterClear = 0L
    t.doSim("bits") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.set #= false; dut.io.clear #= false; dut.io.idx #= 0
      dut.clockDomain.waitSampling(2)
      dut.io.set #= true; dut.io.idx #= 1
      dut.clockDomain.waitSampling()
      dut.io.set #= false
      dut.clockDomain.waitSampling()
      dut.io.set #= true; dut.io.idx #= 3
      dut.clockDomain.waitSampling()
      dut.io.set #= false
      dut.clockDomain.waitSampling(2)
      afterSets = simTime()
      expect(dut.io.flags, 0xA)
      dut.io.clear #= true
      dut.clockDomain.waitSampling()
      dut.io.clear #= false
      dut.clockDomain.waitSampling(2)
      afterClear = simTime()
      expect(dut.io.flags, 0)
    }
    val setLine   = lineOf(ft, "flags(io.idx) := True")
    val clearLine = lineOf(ft, "flags := 0")
    val d = trace(t.pdg, waveOf(t, "bits"), "signal:io_flags", Seq("--at-time", SpinalTraceSim.traceTime(afterSets).toString))
    assert(d.at(ft, setLine).map(_.timestamp).distinct.size == 2, s"both bit writes are providers\n$d")
    assert(d.has(onLine(ft, setLine), withName("input_io_idx"), "Index"), d)
    assert(!d.lines(ft).contains(clearLine), d)
    val c = trace(t.pdg, waveOf(t, "bits"), "signal:io_flags", Seq("--at-time", SpinalTraceSim.traceTime(afterClear).toString))
    assert(c.lines(ft).contains(clearLine) && !c.lines(ft).contains(setLine), s"a full assignment replaces the bit writes\n$c")

    val st = trace(t.pdg, waveOf(t, "bits"), "signal:io_status", Seq("--at-time", SpinalTraceSim.traceTime(afterSets).toString))
    assert(st.lines(ft).contains(lineOf(ft, "status(0) := io.set")) && st.lines(ft).contains(lineOf(ft, "status(1) := io.clear")), st)
  }

  test("BlackBox: opaque node, its output depends on all inputs") {
    val t = compile(new WithBlackBox)
    var at = 0L
    t.doSim("bb") { dut =>
      dut.clockDomain.forkStimulus(10)
      dut.io.x #= 3; dut.io.y #= 4
      dut.clockDomain.waitSampling(2)
      at = simTime()
      expect(dut.io.z, 7)
    }
    val d = trace(t.pdg, waveOf(t, "bb"), "signal:io_z", Seq("--at-time", SpinalTraceSim.traceTime(at).toString))
    val bb = d.nodes.filter(_.name.startsWith("blackbox_adder"))
    assert(bb.nonEmpty, d)
    assert(d.has(_.name.startsWith("blackbox_adder"), onLine(ft, lineOf(ft, "adder.io.a := io.x")), "Data"), d)
    assert(d.has(_.name.startsWith("blackbox_adder"), onLine(ft, lineOf(ft, "adder.io.b := io.y")), "Data"), d)
    assert(PdgFile.statementNames(t.pdg).nonEmpty)
  }
}
