package spinaltrace

import java.io.File
import java.nio.file.Files

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinaltrace.TraceTestKit._
import spinaltrace.examples._

import scala.sys.process._

/** Checks of the Spinal front-end itself: the instrumentation adds no logic, the names it keeps reach
  * the VCD, and the PDG follows the ChiselTrace conventions. */
class InstrumentationSpec extends AnyFunSuite {
  private val designs: Seq[(String, () => Component)] = Seq(
    "GCD" -> (() => new GCD), "WhenChain" -> (() => new WhenChain), "SwitchEnum" -> (() => new SwitchEnum),
    "VecDynamic" -> (() => new VecDynamic), "MuxExample" -> (() => new MuxExample), "HierTop" -> (() => new HierTop),
    "ResetCounter" -> (() => new ResetCounter), "SyncMem" -> (() => new SyncMem), "TwoClockDomains" -> (() => new TwoClockDomains)
  )
  private val roots = ExtractOptions(sourceRoots = Seq(new File(repo, "examples/src")))

  private def rtl(gen: () => Component, instrumented: Boolean): (File, SpinalReport[Component]) = {
    val dir    = Files.createTempDirectory(if (instrumented) "st-inst" else "st-plain").toFile
    val base   = SpinalConfig(targetDirectory = dir.getPath, genLineComments = true)
    val report = if (instrumented) SpinalTrace.elaborate(base)(gen()) else spinalwaves.SpinalWaves.elaborateWithLocations(base)(gen())
    (new File(dir, report.toplevelName + ".v"), report)
  }

  private def yosysAvailable: Boolean = scala.util.Try(Seq("yosys", "-V").!!).isSuccess

  /** Formal equivalence (Yosys equiv_*) of the plain and the instrumented RTL. */
  private def equivalent(plain: File, inst: File, top: String): (Boolean, String) = {
    def load(f: File, as: String) =
      s"read_verilog -sv ${f.getPath}; hierarchy -top $top; proc; memory; flatten; async2sync; " +
        s"delete t:$$print t:$$check t:$$assert; opt_clean; rename $top $as; design -stash $as; "
    val script = load(plain, "gold") + load(inst, "gate") +
      "design -copy-from gold -as gold gold; design -copy-from gate -as gate gate; " +
      "equiv_make gold gate equiv; hierarchy -top equiv; equiv_simple -seq 4; equiv_induct -seq 4; equiv_status -assert"
    val log  = new StringBuilder
    val code = Seq("yosys", "-q", "-p", script).!(ProcessLogger(l => log.append(l).append('\n'), l => log.append(l).append('\n')))
    (code == 0, log.toString)
  }

  test("instrumentation only names existing signals: plain and instrumented RTL are formally equivalent") {
    assume(yosysAvailable, "yosys not on PATH (source spinal-boom/env.sh)")
    for ((name, gen) <- designs) {
      val (plain, _)    = rtl(gen, instrumented = false)
      val (inst, rep)   = rtl(gen, instrumented = true)
      val plainText     = scala.io.Source.fromFile(plain).mkString
      val instText      = scala.io.Source.fromFile(inst).mkString
      def ports(t: String) = "(?m)^\\s*(input|output|inout)\\b.*$".r.findAllIn(t).map(_.trim).toSeq.sorted
      // Verilog `reg`s (flip-flops and always-block wires) except anonymous ones and the ones SpinalTrace named
      val named = scala.collection.mutable.HashSet[String]()
      rep.toplevel.walkComponents(_.dslBody.walkDeclarations {
        case bt: BaseType if bt.hasTag(SpinalTraceNamedTag) => named += bt.getName()
        case _                                              =>
      })
      def regs(t: String) = "(?m)^\\s*reg\\b[^;]*;".r.findAllIn(t).map(_.replaceAll("\\s+", " ").trim)
        .filterNot(r => r.matches(".*\\b_zz_\\w*;") || named.exists(n => r.endsWith(s" $n;"))).toSeq.sorted
      assert(ports(plainText) == ports(instText), s"$name: ports changed")
      assert(regs(plainText) == regs(instText), s"$name: registers changed")
      val (ok, log) = equivalent(plain, inst, rep.toplevelName)
      assert(ok, s"$name: instrumented RTL is not equivalent to the plain RTL\n$log")
    }
  }

  test("every predicate and probe signal of the PDG is present in the Verilator VCD") {
    for ((name, gen) <- designs) {
      val t = SpinalTraceSim.compile(SimConfig.workspacePath(simWorkspace), SpinalTraceSimOptions(extract = roots))(gen())
      val stale = spinalwaves.SpinalCompat.waveFile(t.compiled, "vcd")
      stale.getParentFile.mkdirs()
      Files.writeString(stale.toPath, "stale waveform")
      assert(t.waveFile("vcd").isEmpty, "an unstarted run exposed an old waveform")
      t.doSim("vcd") { dut =>
        dut.clockDomain.forkStimulus(10)
        dut match {
          case d: TwoClockDomains => d.cdB.forkStimulus(14)
          case _                  =>
        }
        dut.clockDomain.waitSampling(3)
      }
      val vcd   = waveOf(t, "vcd")
      val vars  = VcdHeader.varPaths(vcd)
      val pdg   = ujson.read(scala.io.Source.fromFile(t.pdg).mkString)
      val scope = pdg("spinaltrace")("extraScopes").arr.map(_.str).mkString(".")
      val probes = pdg("predicates").arr.map(_("name").str) ++
        (pdg("vertices").arr ++ pdg("edges").arr).flatMap(v => v("condition") match {
          case ujson.Null => Nil
          case c          => c("probeName").arr.map(_.str)
        })
      val missing = probes.distinct.filterNot(p => vars.contains(s"$scope.$p"))
      assert(missing.isEmpty, s"$name: not in the VCD: ${missing.mkString(", ")}")
    }
  }

  test("PDG of the GCD follows the ChiselTrace vertex/edge conventions") {
    val (_, report) = rtl(() => new GCD, instrumented = true)
    val pdg   = PdgExtractor.extract(report, roots)
    val names = pdg.vertices.map(_.name)
    Seq("input_io_a", "input_io_b", "input_io_loadValues", "output_io_result", "defreg_x", "defreg_y",
      "connect_io_result", "cond_on_[io_loadValues]").foreach(n => assert(names.contains(n), names))
    assert(names.count(_ == "connect_x") == 2 && names.count(_ == "connect_y") == 2)
    assert(!names.exists(_.contains("clk")) && !names.exists(_.contains("tmp")), names) // clock plumbing and pruned tmp
    val x = pdg.vertices.filter(_.name == "connect_x")
    assert(x.forall(v => v.clocked && v.assignsTo.contains("x") && v.isChiselStatement && v.relatedSignal.contains(("x", ""))))
    val a = pdg.vertices.find(_.name == "input_io_a").get
    assert(a.kind == PdgModel.VertexKind.IO && a.relatedSignal.contains(("io", "a")))
    assert(a.loc.file.endsWith("examples/src/spinaltrace/examples/Gcd.scala") && new File(a.loc.file).isAbsolute)
    val cond = pdg.vertices.find(_.name.startsWith("cond_on_[y, x]")).get
    assert(cond.kind == PdgModel.VertexKind.ControlFlow)
    // the auto-named `when_Gcd_l19` signal is compiler generated
    assert(pdg.vertices.exists(v => v.assignsTo.contains("when_Gcd_l19") && !v.isChiselStatement && v.relatedSignal.isEmpty))
    assert(pdg.predicates.map(_.name) == Seq("when_Gcd_l19", "io_loadValues"))
    val kinds = pdg.edges.map(_.kind).toSet
    assert(kinds == Set("Data", "Conditional", "Declaration"), kinds)
    assert(pdg.meta.clockDomains.map(_.clock) == Seq("clk") && pdg.meta.clockDomains.head.reset.contains("reset"))
    assert(pdg.meta.extraScopes == Seq("TOP", "GCD"))
  }

  test("dynamic Vec writes become per-element vertices with a condition on the (named) index") {
    val (_, report) = rtl(() => new VecDynamic, instrumented = true)
    val pdg   = PdgExtractor.extract(report, roots)
    val writes = pdg.vertices.filter(v => v.name.startsWith("connect_regs_"))
    assert(writes.size == 4)
    assert(writes.map(_.condition.get).map(c => (c.probeName, c.probeValue)).toSet ==
      (0 until 4).map(i => (Seq("io_wrIdx"), Seq(BigInt(i)))).toSet)
    assert(pdg.vertices.exists(_.name == "defnode_probe_io_wrIdx") && pdg.vertices.exists(_.name == "defnode_probe_io_rdIdx"))
    val read = pdg.vertices.indexWhere(_.name == "connect_io_rdData")
    val conds = pdg.edges.filter(e => e.from == read && e.kind == "Data").flatMap(_.condition).map(_.probeValue.head).toSet
    assert(conds == (0 until 4).map(BigInt(_)).toSet)
  }

  test("switch becomes a case fork (SpinalTrace CFG extension) with enum encodings as patterns") {
    val (_, report) = rtl(() => new SwitchEnum, instrumented = true)
    val json = PdgModel.toJson(PdgExtractor.extract(report, roots))
    val sw   = json("cfg").arr.find(_.obj.contains("cases")).getOrElse(fail("no switch node"))
    val keys = sw("cases").arr.map(_("keys").arr.map(_("pattern").str).toSeq).toSeq
    assert(keys == Seq(Seq("00"), Seq("01")), keys)
    assert(sw.obj.contains("defaultBranch"))
  }

  test("sync-read memory: delayed read vertex and per-word write vertices with address and enable conditions") {
    val (_, report) = rtl(() => new SyncMem, instrumented = true)
    val pdg  = PdgExtractor.extract(report, roots)
    val read = pdg.vertices.find(_.name == "connect_io_rdData").get
    assert(read.assignDelay == 1)
    val writes = pdg.vertices.filter(_.name.startsWith("connect_mem."))
    assert(writes.size == 8 && writes.forall(_.clocked))
    val c = writes.find(_.name == "connect_mem.3").get.condition.get
    assert(c.probeName.size == 2 && c.probeName.contains("io_wrAddr") && c.probeValue.contains(BigInt(3)))
    assert(c.probeName.exists(_.startsWith("mem_wen_Features_l")), c)
  }

  test("two clock domains are reported (ChiselTrace limitation: one clock)") {
    val (_, report) = rtl(() => new TwoClockDomains, instrumented = true)
    val pdg = PdgExtractor.extract(report, roots)
    assert(pdg.meta.clockDomains.size == 2, pdg.meta.clockDomains)
    assert(pdg.meta.warnings.exists(_.contains("2 clock domains")), pdg.meta.warnings)
  }
}

/** Tiny VCD header reader: dotted paths of all variables. */
object VcdHeader {
  def varPaths(vcd: File): Set[String] = {
    val src   = scala.io.Source.fromFile(vcd)
    val scope = scala.collection.mutable.Stack[String]()
    val out   = scala.collection.mutable.HashSet[String]()
    try {
      val it = src.getLines().takeWhile(!_.contains("$enddefinitions"))
      for (line <- it) {
        val t = line.trim.split("\\s+")
        t.headOption match {
          case Some("$scope")   => scope.push(t(2))
          case Some("$upscope") => scope.pop()
          case Some("$var")     => out += (scope.reverse :+ t(4)).mkString(".")
          case _                =>
        }
      }
    } finally src.close()
    out.toSet
  }
}
