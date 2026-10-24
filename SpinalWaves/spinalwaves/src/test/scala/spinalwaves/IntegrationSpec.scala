package spinalwaves

import java.nio.file.{Files, Path, Paths}
import scala.collection.mutable
import scala.sys.process.{Process, ProcessLogger}
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinalwaves.examples._

/** Every scenario exercises real Verilator output through the Rust typed-wave loader. */
trait IntegrationChecks { self: AnyFunSuite =>
  protected def compile[T <: Component](name: String)(gen: => T): SpinalWavesCompiled[T] =
    SpinalWavesSim(SimConfig.workspacePath(s"target/integration/$name"), launchViewer = false).compile(gen)

  protected def document[T <: Component](sim: SpinalWavesCompiled[T]): ujson.Value =
    ujson.read(Files.readString(sim.hglddFile))

  protected def module(doc: ujson.Value, name: String): ujson.Value =
    doc("objects").arr.find(o => o("kind").str == "module" && o("obj_name").str == name).get

  protected def field(doc: ujson.Value, variable: ujson.Value, name: String): ujson.Value = {
    val struct = doc("objects").arr.find(_("obj_name").str == variable("type_name").str).get
    struct("port_vars").arr.find(_("var_name").str == name).get
  }

  protected def root(doc: ujson.Value, top: String, name: String): ujson.Value =
    module(doc, top)("port_vars").arr.find(_("var_name").str == name).get

  protected def typeName(v: ujson.Value): String = v("source_lang_type_info")("type_name").str

  protected def rawVcdValues(vcd: Path, signal: String): Set[BigInt] = {
    val lines = Files.readString(vcd).linesIterator.toVector
    val declarations = lines.map(_.trim.split("\\s+")).filter(t => t.length >= 6 && t(0) == "$var" && t(4) == signal)
    assert(declarations.nonEmpty, s"No VCD declaration for $signal")
    val code = declarations.head(3)
    lines.iterator.map(_.trim.split("\\s+")).collect {
      case tokens if tokens.length == 2 && tokens(1) == code && tokens(0).startsWith("b") &&
        tokens(0).drop(1).forall(c => c == '0' || c == '1') => BigInt(tokens(0).drop(1), 2)
    }.toSet
  }

  protected def source(doc: ujson.Value, v: ujson.Value, declaration: String): Unit = {
    val loc = v("hgl_loc")
    val file = doc("HGLDD")("file_info")(loc("file").num.toInt - 1).str
    assert(Paths.get(file).isAbsolute)
    assert(file.endsWith("/spinalwaves/examples/Designs.scala"))
    val lines = Files.readString(Paths.get(file)).linesIterator.toVector
    val matches = lines.zipWithIndex.filter(_._1.trim == declaration)
    assert(matches.size == 1, s"Source fixture declaration must be unique: $declaration")
    val line = matches.head._2 + 1
    assert(loc("begin_line").num.toInt == line)
    assert(loc("end_line").num.toInt == line)
  }

  /** Independently expand HGLDD structs/array dimensions and compare all physical signal names. */
  private def checkNaming[T <: Component](sim: SpinalWavesCompiled[T], doc: ujson.Value): Unit = {
    val objects = doc("objects").arr.map(o => o("obj_name").str -> o).toMap
    def expand(v: ujson.Value, value: ujson.Value, path: Seq[String]): Seq[(String, String)] = {
      val dims = v.obj.get("unpacked_range").map(_.arr.toVector).getOrElse(Vector.empty)
      if (dims.nonEmpty) {
        val hi = dims(0).num.toInt
        val lo = dims(1).num.toInt
        val element = ujson.read(ujson.write(v))
        element.obj.remove("unpacked_range")
        if (dims.size > 2) element("unpacked_range") = ujson.Arr.from(dims.drop(2))
        val indices = (math.min(lo, hi) to math.max(lo, hi))
        assert(value("operands").arr.size == indices.size)
        indices.zip(value("operands").arr).flatMap { case (i, expr) => expand(element, expr, path :+ i.toString) }
      } else if (v("type_name").str == "logic") {
        Seq(path.mkString(".") -> value("sig_name").str)
      } else {
        val fields = objects(v("type_name").str)("port_vars").arr
        val expressions = value("operands").arr
        assert(fields.size == expressions.size)
        fields.zip(expressions).flatMap { case (f, expr) => expand(f, expr, path :+ f("var_name").str) }.toSeq
      }
    }
    def visit(c: Component, scope: ujson.Value): Unit = {
      val prefix = HglNaming.instancePath(c)
      val canonical = objects(c.definitionName)
      val emitted = scope.obj.getOrElse("port_vars", canonical("port_vars")).arr.flatMap { v =>
        expand(v, v("value"), Seq(v("var_name").str))
      }
      val expected = mutable.ArrayBuffer.empty[(String, String)]
      c.dslBody.walkDeclarations {
        case bt: BaseType if bt.isNamed && bt.getName().nonEmpty && bt.getBitsWidth > 0 &&
          !sim.report.prunedSignals.contains(bt) =>
          val (typedRoot, fields) = HglNaming.hglPath(bt)
          val typed = Seq(typedRoot, fields).filter(_.nonEmpty).mkString(".")
          assert(HglNaming.rtlPath(bt) == (prefix :+ bt.getName()).mkString("."))
          expected += typed -> HglNaming.rtlPath(bt)
        case _ => ()
      }
      val expanded = emitted.map { case (typed, rtl) =>
        (prefix :+ typed).mkString(".") -> (prefix :+ rtl).mkString(".")
      }
      assert(expanded.distinct.size == expanded.size)
      assert(expanded.toSet == expected.toSet)
      val children = scope.obj.getOrElse("children", canonical("children")).arr
      c.children.foreach { child =>
        val instance = children.find(_("name").str == child.getName()).get
        visit(child, instance)
      }
    }
    visit(sim.dut, objects(sim.dut.definitionName))
  }

  protected def verify[T <: Component](sim: SpinalWavesCompiled[T]): ujson.Value = {
    assert(sim.report.generatedSourcesPaths.nonEmpty)
    sim.report.generatedSourcesPaths.foreach(path => assert(Files.isRegularFile(Paths.get(path)), s"Missing generated RTL: $path"))
    assert(Files.size(sim.vcdFile) > 0)
    assert(sim.extraScopes == SimLayout.extraScopes(sim.vcdFile, sim.report.toplevelName))
    info(s"VCD=${sim.vcdFile}; extraScopes=${sim.extraScopes.mkString(" ")}")
    val doc = document(sim)
    checkNaming(sim, doc)
    val configured = sys.env.get("SPINALWAVES_CHECK").map(Paths.get(_))
    val checker = configured.getOrElse(Seq("release", "debug")
      .map(profile => Paths.get(s"../tools/spinalwaves-check/target/$profile/spinalwaves-check"))
      .find(Files.isExecutable(_)).getOrElse(Paths.get("../tools/spinalwaves-check/target/release/spinalwaves-check")))
    assert(Files.isExecutable(checker), s"Build the Rust checker first: $checker")
    val output = new StringBuilder
    val reportPath = sim.workspace.resolve("spinalwaves/check.json")
    val rewritten = sim.workspace.resolve("spinalwaves/typed.vcd")
    val command = Seq(checker.toAbsolutePath.toString, "--vcd", sim.vcdFile.toAbsolutePath.toString,
      "--hgldd", sim.hglddDir.toAbsolutePath.toString, "--top-module", sim.report.toplevelName,
      "--json", reportPath.toAbsolutePath.toString, "--out", rewritten.toAbsolutePath.toString,
      "--extra-scopes") ++ sim.extraScopes
    val status = Process(command).!(ProcessLogger(s => output.append(s).append('\n'), s => output.append(s).append('\n')))
    assert(status == 0, s"Rust typed-wave validation failed:\n$output")
    val checked = ujson.read(Files.readString(reportPath))
    assert(checked("ok").bool)
    assert(checked("counts")("leaves").num > 0)
    for (key <- Seq("scopes_missing", "missing", "width_mismatch", "unsupported", "find_trace_failed", "dropped"))
      assert(checked("counts")(key).num == 0, s"Rust checker reported $key: $checked")
    assert(Files.size(rewritten) > 0)
    info(output.toString)
    doc
  }
}

class IntegrationSpec extends AnyFunSuite with IntegrationChecks {
  test("GCD register example resolves typed waves and exact source locations") {
    val sim = compile("gcd")(new Gcd())
    sim.doSim("gcd", 42) { dut =>
      dut.io.load #= false
      dut.io.a #= 0
      dut.io.b #= 0
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(3)
      for ((a, b, answer) <- Seq((48, 18, 6), (270, 192, 6), (17, 13, 1), (121, 11, 11),
        (0, 35, 35), (35, 0, 35), (0, 0, 0))) {
        dut.io.a #= a
        dut.io.b #= b
        dut.io.load #= true
        dut.clockDomain.waitSampling()
        dut.io.load #= false
        dut.clockDomain.waitSampling()
        var cycles = 0
        while (!dut.io.valid.toBoolean && cycles < 300) {
          dut.clockDomain.waitSampling()
          cycles += 1
        }
        assert(cycles < 300)
        assert(dut.io.result.toInt == answer)
      }
    }
    val doc = verify(sim)
    val x = root(doc, sim.report.toplevelName, "x")
    assert(typeName(x) == "Reg UInt(16 bits)")
    source(doc, x, "val x = Reg(UInt(width bits)) init 0")
    val io = root(doc, sim.report.toplevelName, "io")
    assert(typeName(field(doc, io, "a")) == "in UInt(16 bits)")
    source(doc, field(doc, io, "a"), "val a = in UInt(width bits)")
  }

  test("nested Bundle Vec Vec-of-Bundle and fixed points retain their types") {
    val sim = compile("structured")(new Structured)
    sim.doSim("structures", 43) { dut =>
      for (step <- 0 until 6) {
        for (lane <- 0 until 2) {
          dut.io.input.lanes(lane).signed #= -30 + step + lane
          dut.io.input.lanes(lane).flags #= (step + lane) % 8
          dut.io.input.lanes(lane).valid #= ((step + lane) % 2 == 0)
          for (column <- 0 until 2) dut.io.input.matrix(lane)(column) #= step * 4 + lane * 2 + column
        }
        sleep(10)
        assert(dut.io.output.lanes(1).signed.toInt == -29 + step)
        assert(dut.io.output.matrix(1)(1).toInt == step * 4 + 3)
        assert(dut.io.signedFixed.raw.toInt == -30 + step)
        assert(dut.io.unsignedFixed.raw.toInt == step * 4)
      }
    }
    val doc = verify(sim)
    val io = root(doc, sim.report.toplevelName, "io")
    val output = field(doc, io, "output")
    val lanes = field(doc, output, "lanes")
    assert(typeName(output) == "out Samples")
    assert(typeName(lanes) == "out Vec[Sample](2)")
    assert(lanes("unpacked_range") == ujson.Arr(1, 0))
    assert(typeName(field(doc, lanes, "signed")) == "out SInt(9 bits)")
    assert(typeName(field(doc, lanes, "flags")) == "out Bits(3 bits)")
    assert(typeName(field(doc, lanes, "valid")) == "out Bool")
    assert(field(doc, output, "matrix")("unpacked_range") == ujson.Arr(1, 0, 1, 0))
    assert(typeName(field(doc, output, "matrix")) == "out Vec[Vec[UInt(7 bits)](2)](2)")
    assert(typeName(field(doc, io, "signedFixed")).contains("SFix(maxExp=4, 12 bits)"))
    assert(typeName(field(doc, io, "unsignedFixed")).contains("UFix(maxExp=4, 12 bits)"))
    source(doc, field(doc, lanes, "signed"), "val signed = SInt(9 bits)")
    assert(HglNaming.hglPath(sim.dut.io.signedFixed.raw) == ("io", "signedFixed"))
  }

  test("explicit inferred and custom enum encodings use actual RTL values") {
    val sim = compile("encodings")(new Encodings)
    sim.doSim("enums", 44) { dut =>
      dut.io.advance #= false
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(3)
      for (step <- 0 until 9) {
        dut.io.advance #= true
        dut.clockDomain.waitSampling()
        dut.io.advance #= false
        dut.clockDomain.waitSampling()
        assert(dut.io.oneHot.toEnum.position == (step + 1) % 3)
        assert(dut.io.oneHot.toEnum == dut.io.customState.toEnum)
        assert(dut.io.inferredState.toEnum == dut.io.customState.toEnum)
      }
    }
    assert(rawVcdValues(sim.vcdFile, "io_oneHot") == Set(BigInt(1), BigInt(2), BigInt(4)))
    assert(rawVcdValues(sim.vcdFile, "io_inferredState") == Set(BigInt(1), BigInt(2), BigInt(4)))
    assert(rawVcdValues(sim.vcdFile, "io_customState") == Set(BigInt(5), BigInt(1), BigInt(6)))
    val doc = verify(sim)
    val top = module(doc, sim.report.toplevelName)
    val io = root(doc, sim.report.toplevelName, "io")
    def codes(name: String): Map[String, String] = {
      val v = field(doc, io, name)
      assert(typeName(v) == "out TrafficState")
      top("enum_defs")(v("enum_def_ref").num.toInt.toString).obj.map { case (k, value) => k -> value.str }.toMap
    }
    assert(codes("oneHot") == Map("1" -> "Idle", "2" -> "Busy", "4" -> "Done"))
    assert(codes("inferredState") == codes("oneHot"))
    assert(codes("customState") == Map("5" -> "Idle", "1" -> "Busy", "6" -> "Done"))
    assert(field(doc, io, "customState")("packed_range") == ujson.Arr(2, 0))
    source(doc, root(doc, sim.report.toplevelName, "state"), "val state = Reg(states(binaryOneHot)) init Idle")
  }

  test("same-module child instances and nested Areas retain independent paths") {
    val sim = compile("hierarchy")(new Hierarchy)
    sim.doSim("hierarchy", 45) { dut =>
      dut.io.input #= 0
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(3)
      for (i <- 0 until 6) {
        dut.io.input #= i * 20
        dut.clockDomain.waitSampling()
        assert(dut.io.first.toInt == i * 20 + 1)
        assert(dut.io.second.toInt == i * 20 + 2)
      }
    }
    val doc = verify(sim)
    val children = module(doc, sim.report.toplevelName)("children").arr
    assert(children.map(_("name").str).toSet == Set("left", "right"))
    assert(children.map(_("module_name").str).distinct.size == 1)
    source(doc, children.find(_("name").str == "left").get, "class Incrementer(val width: Int = 8) extends Component {")
    source(doc, children.find(_("name").str == "right").get, "class Incrementer(val width: Int = 8) extends Component {")
    assert(HglNaming.hglPath(sim.dut.left.io.input) == ("left.io", "input"))
    assert(HglNaming.hglPath(sim.dut.right.io.input) == ("right.io", "input"))
    assert(HglNaming.hglPath(sim.dut.work.inner.wrapped) == ("work", "inner.wrapped"))
    val work = root(doc, sim.report.toplevelName, "work")
    assert(typeName(field(doc, work, "count")) == "Reg UInt(8 bits)")
  }

  test("Stream and Flow preserve payload typing and opposite ready direction") {
    val sim = compile("protocols")(new Protocols)
    sim.doSim("protocols", 46) { dut =>
      for (i <- 0 until 8) {
        dut.io.input.valid #= ((i & 1) != 0)
        dut.io.input.payload.signed #= i - 4
        dut.io.input.payload.flags #= i
        dut.io.input.payload.valid #= true
        dut.io.output.ready #= ((i & 2) != 0)
        sleep(10)
        assert(dut.io.input.ready.toBoolean == ((i & 2) != 0))
        assert(dut.io.output.payload.signed.toInt == i - 4)
        assert(dut.io.monitor.valid.toBoolean == ((i & 3) == 3))
      }
    }
    val doc = verify(sim)
    val io = root(doc, sim.report.toplevelName, "io")
    val input = field(doc, io, "input")
    assert(typeName(input) == "Stream[Sample]")
    assert(typeName(field(doc, input, "ready")) == "out Bool")
    assert(typeName(field(doc, input, "valid")) == "in Bool")
    assert(typeName(field(doc, io, "monitor")) == "out Flow[Sample]")
  }

  test("library StateMachine generated enum is visible and decodes") {
    val sim = compile("fsm")(new LibraryFsm)
    sim.doSim("fsm", 47) { dut =>
      dut.io.advance #= false
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(3)
      for (_ <- 0 until 4) {
        dut.io.advance #= true
        dut.clockDomain.waitSampling()
        dut.io.advance #= false
        dut.clockDomain.waitSampling()
        assert(dut.io.busy.toBoolean)
        dut.io.advance #= true
        dut.clockDomain.waitSampling()
        dut.io.advance #= false
        dut.clockDomain.waitSampling()
        assert(!dut.io.busy.toBoolean)
      }
    }
    val doc = verify(sim)
    val definitions = module(doc, sim.report.toplevelName)("enum_defs").obj.values
    assert(definitions.exists(d => d.obj.values.map(_.str).toSet.contains("active")))
  }
}
