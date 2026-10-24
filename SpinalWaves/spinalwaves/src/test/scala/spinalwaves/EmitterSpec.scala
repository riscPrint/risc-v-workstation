package spinalwaves

import java.nio.file.{Files, Paths}
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class PruningTop(val width: Int = 8) extends Component {
  val io = new Bundle {
    val a = in UInt(width bits)
    val result = out UInt(width bits)
  }
  val forgotten = UInt(width bits)
  forgotten := io.a + 7
  io.result := io.a + 1
}

class EmitterSpec extends AnyFunSuite {
  test("typed elaboration leaves generated Verilog unchanged and omits pruned declarations") {
    val config = SpinalConfig(targetDirectory = "target/plain-rtl", headerWithDate = false, headerWithRepoHash = false)
    val plain = config.generateVerilog(new PruningTop)
    val located = SpinalWaves.elaborateWithLocations(config.copy(targetDirectory = "target/located-rtl"))(new PruningTop)
    val before = Files.readString(Paths.get(plain.generatedSourcesPaths.head))
    val after = Files.readString(Paths.get(located.generatedSourcesPaths.head))
    assert(before == after)
    assert(located.prunedSignals.exists(_.getName() == "forgotten"))
    val out = HglddEmitter.emit(located, Paths.get("target/emitter"))
    val doc = ujson.read(Files.readString(out))
    val modules = doc("objects").arr.filter(_("kind").str == "module")
    assert(modules.size == 1)
    assert(modules.head("module_name").str == located.toplevelName)
    assert(!modules.head("port_vars").arr.exists(_("var_name").str == "forgotten"))
    val info = modules.head("source_lang_type_info")
    assert(info("params").arr.exists(p => p("name").str == "width" && p("value").str == "8"))
    assert(doc("HGLDD")("file_info").arr.forall(p => Paths.get(p.str).isAbsolute))
    val ioStruct = doc("objects").arr.find(o => o("obj_name").str == "PruningTop_io_struct").get
    val a = ioStruct("port_vars").arr.find(_("var_name").str == "a").get
    assert(a("source_lang_type_info")("type_name").str == "in UInt(8 bits)")
    assert(a("hgl_loc")("begin_line").num.toInt == 9)
    assert(Files.readString(out).contains("\"sig_name\": \"io_a\""))
  }
  test("discovery does not run enum naming or change singleton-enum RTL") {
    val config = SpinalConfig(targetDirectory = "target/plain-enum-rtl", headerWithDate = false, headerWithRepoHash = false)
    val plain = config.generateVerilog(new SingletonEnumTop)
    val located = SpinalWaves.elaborateWithLocations(config.copy(targetDirectory = "target/located-enum-rtl"))(new SingletonEnumTop)
    assert(Files.readString(Paths.get(plain.generatedSourcesPaths.head)) ==
      Files.readString(Paths.get(located.generatedSourcesPaths.head)))
    assert(ProbeState.Start.getName() == "Start")
    assert(ProbeState.Done.getName() == "Done")
    val out = HglddEmitter.emit(located, Paths.get("target/emitter-enum"))
    val module = ujson.read(Files.readString(out))("objects").arr.find(_("kind").str == "module").get
    assert(module("enum_defs")("0").obj.values.map(_.str).toSet == Set("Start", "Done"))
  }

  test("partially pruned bundles and sparse Vecs preserve surviving field paths") {
    val report = SpinalWaves.elaborateWithLocations(SpinalConfig(targetDirectory = "target/sparse-rtl"))(new SparseTop)
    val out = HglddEmitter.emit(report, Paths.get("target/sparse"))
    val doc = ujson.read(Files.readString(out))
    val objects = doc("objects").arr.map(o => o("obj_name").str -> o).toMap
    val vars = objects("SparseTop")("port_vars").arr.map(v => v("var_name").str -> v).toMap
    val lanes = vars("lanes")
    assert(!lanes.obj.contains("unpacked_range"))
    assert(objects(lanes("type_name").str)("port_vars").arr.map(_("var_name").str).toSeq == Seq("1"))
    val pair = objects(vars("pair")("type_name").str)("port_vars").arr
    assert(pair.map(_("var_name").str).toSeq == Seq("live"))
    assert(HglNaming.hglPath(report.toplevel.lanes(1)) == ("lanes", "1"))
    assert(!Files.readString(out).contains("lanes_0"))
    assert(!Files.readString(out).contains("pair_gone"))
  }

  test("location elaboration preserves explicit SystemVerilog mode") {
    val config = SpinalConfig(mode = SystemVerilog, targetDirectory = "target/plain-sv",
      headerWithDate = false, headerWithRepoHash = false)
    val plain = config.generateSystemVerilog(new PruningTop)
    val located = SpinalWaves.elaborateWithLocations(config.copy(targetDirectory = "target/located-sv"))(new PruningTop)
    assert(located.generatedSourcesPaths.head.endsWith(".sv"))
    assert(Files.readString(Paths.get(plain.generatedSourcesPaths.head)) ==
      Files.readString(Paths.get(located.generatedSourcesPaths.head)))
  }

  test("source locator keeps a deterministic bare-name fallback") {
    val frame = new StackTraceElement("example.Missing", "build", "NoSuchSource.scala", 17)
    assert(SourceLocator.fromFrame(frame, Seq.empty) == SourceLocation("NoSuchSource.scala", 17, 1))
  }
}

class SparseTop extends Component {
  val io = new Bundle {
    val input = in UInt(8 bits)
    val output = out UInt(8 bits)
    val other = out UInt(8 bits)
  }
  val lanes = Vec(UInt(8 bits), 3)
  lanes(0) := io.input
  lanes(1) := io.input + 1
  lanes(2) := io.input + 2
  val pair = new Bundle {
    val live = UInt(8 bits)
    val gone = UInt(8 bits)
  }
  pair.live := io.input + 3
  pair.gone := io.input + 4
  io.output := lanes(1)
  io.other := pair.live
}

object ProbeState extends SpinalEnum {
  val Start, Done = newElement()
}
class SingletonEnumTop extends Component {
  val io = new Bundle {
    val go = in Bool()
    val state = out(ProbeState())
  }
  val state = Reg(ProbeState()) init ProbeState.Start
  when(io.go) { state := ProbeState.Done }
  io.state := state
}
