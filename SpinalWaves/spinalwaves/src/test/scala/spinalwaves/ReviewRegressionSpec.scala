package spinalwaves

import java.nio.file.{Files, Paths}
import java.nio.file.attribute.FileTime
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class ReviewCollisionsAndVec extends Component {
  val io = new Bundle {
    val input = in UInt(8 bits)
    val a_b = out(new Bundle { val c = new Bundle { val left = UInt(5 bits) } })
    val a = out(new Bundle { val b_c = new Bundle { val right = Bits(3 bits) } })
    val values = out Vec(UInt(8 bits), 12)
  }
  io.a_b.c.left := io.input.resize(5)
  io.a.b_c.right := io.input.asBits.resize(3)
  for (i <- 0 until 12) io.values(i) := io.input + i
}

class ReviewFlatChild(val label: String) extends Component {
  val io = new Bundle {
    val a_b = in UInt(8 bits)
    val result = out UInt(8 bits)
  }
  io.result := io.a_b + 1
}

class ReviewNestedChild(val label: String) extends Component {
  val io = new Bundle {
    val a = new Bundle { val b = in UInt(8 bits) }
    val result = out UInt(8 bits)
  }
  io.result := io.a.b + 1
}

/** The two Scala leaf shapes and every wrapper generate identical respective RTL modules. */
class ReviewWrapper(val nested: Boolean, val label: String) extends Component {
  val io = new Bundle {
    val input = in UInt(8 bits)
    val output = out UInt(8 bits)
  }
  val child = if (nested) {
    val leaf = new ReviewNestedChild(label)
    leaf.io.a.b := io.input
    io.output := leaf.io.result
    leaf
  } else {
    val leaf = new ReviewFlatChild(label)
    leaf.io.a_b := io.input
    io.output := leaf.io.result
    leaf
  }
  child.setName("child")
}

class ReviewDeduplicated extends Component {
  val io = new Bundle {
    val input = in UInt(8 bits)
    val outputs = out Vec(UInt(8 bits), 3)
  }
  val left = new ReviewWrapper(nested = false, label = "flat-left")
  val right = new ReviewWrapper(nested = true, label = "nested-right")
  val other = new ReviewWrapper(nested = false, label = "flat-other")
  Seq(left, right, other).zipWithIndex.foreach { case (wrapper, i) =>
    wrapper.io.input := io.input + i
    io.outputs(i) := wrapper.io.output
  }
}

class ReviewWavePath extends Component {
  val io = new Bundle {
    val input = in UInt(8 bits)
    val output = out UInt(8 bits)
  }
  io.output := io.input + 1
}

class ReviewRegressionSpec extends AnyFunSuite with IntegrationChecks {
  test("colliding struct path spellings stay unique and Vec12 uses numeric array order") {
    val sim = compile("review-collisions")(new ReviewCollisionsAndVec)
    sim.doSim("collisions", 71) { dut =>
      for (value <- Seq(3, 18, 29)) {
        dut.io.input #= value
        sleep(10)
        assert(dut.io.a_b.c.left.toInt == value)
        assert(dut.io.a.b_c.right.toInt == (value & 7))
        for (i <- 0 until 12) assert(dut.io.values(i).toInt == value + i)
      }
    }
    val doc = verify(sim)
    val names = doc("objects").arr.map(_("obj_name").str)
    assert(names.distinct.size == names.size)
    val io = root(doc, sim.report.toplevelName, "io")
    val left = field(doc, field(doc, io, "a_b"), "c")
    val right = field(doc, field(doc, io, "a"), "b_c")
    assert(left("type_name").str != right("type_name").str)
    assert(typeName(field(doc, left, "left")) == "out UInt(5 bits)")
    assert(typeName(field(doc, right, "right")) == "out Bits(3 bits)")
    val values = field(doc, io, "values")
    assert(values("type_name").str == "logic")
    assert(values("unpacked_range") == ujson.Arr(11, 0))
    assert(values("packed_range") == ujson.Arr(7, 0))
    assert(typeName(values) == "out Vec[UInt(8 bits)](12)")
    val ioValues = root(doc, sim.report.toplevelName, "io")("value")("operands").arr
    val ioFields = doc("objects").arr.find(_("obj_name").str == io("type_name").str).get("port_vars").arr
    val expression = ioValues(ioFields.indexWhere(_("var_name").str == "values"))
    assert(expression("operands").arr.map(_("sig_name").str).toSeq == (0 until 12).map(i => s"io_values_$i"))
  }

  test("deduplicated RTL preserves nested instance shapes classes and constructor parameters") {
    val sim = compile("review-dedup")(new ReviewDeduplicated)
    sim.doSim("dedup", 72) { dut =>
      for (value <- Seq(1, 21, 97)) {
        dut.io.input #= value
        sleep(10)
        for (i <- 0 until 3) assert(dut.io.outputs(i).toInt == value + i + 1)
      }
    }
    val doc = verify(sim)
    val definitions = doc("objects").arr.filter(_("kind").str == "module")
    val allComponents = Seq[Component](sim.dut, sim.dut.left, sim.dut.right, sim.dut.other,
      sim.dut.left.child, sim.dut.right.child, sim.dut.other.child)
    val rtlDefinitions = allComponents.map(_.definitionName).toSet
    assert(definitions.size == rtlDefinitions.size)
    assert(definitions.map(_("module_name").str).toSet == rtlDefinitions)
    val wrappers = module(doc, sim.report.toplevelName)("children").arr
    assert(wrappers.map(_("module_name").str).distinct.size == 1)
    val leaves = wrappers.map(_("children")(0))
    assert(leaves.map(_("module_name").str).distinct.size == 1)
    def parameter(instance: ujson.Value, name: String): String =
      instance("source_lang_type_info")("params").arr.find(_("name").str == name).get("value").str
    for ((name, nested, label) <- Seq(("left", false, "flat-left"), ("right", true, "nested-right"),
      ("other", false, "flat-other"))) {
      val wrapper = wrappers.find(_("name").str == name).get
      assert(typeName(wrapper) == "ReviewWrapper")
      assert(parameter(wrapper, "nested") == nested.toString)
      assert(parameter(wrapper, "label") == label)
      val leaf = wrapper("children")(0)
      assert(leaf("name").str == "child")
      assert(typeName(leaf) == (if (nested) "ReviewNestedChild" else "ReviewFlatChild"))
      assert(parameter(leaf, "label") == label)
      val io = leaf("port_vars").arr.find(_("var_name").str == "io").get
      if (nested) assert(typeName(field(doc, field(doc, io, "a"), "b")) == "in UInt(8 bits)")
      else assert(typeName(field(doc, io, "a_b")) == "in UInt(8 bits)")
    }
    val flat = sim.dut.left.child.asInstanceOf[ReviewFlatChild]
    val nested = sim.dut.right.child.asInstanceOf[ReviewNestedChild]
    assert(HglNaming.hglPath(flat.io.a_b) == ("left.child.io", "a_b"))
    assert(HglNaming.hglPath(nested.io.a.b) == ("right.child.io", "a.b"))
  }

  test("external waveform paths honor TEST prefixes repeated names and unrelated VCD files") {
    val external = Paths.get("target/review-external-waves").toAbsolutePath.normalize
    val config = SimConfig.workspacePath("target/integration/review-wave-path")
      .setTestPath(external.resolve("$TEST").toString).waveFilePrefix("capture_$TEST")
    val phases = config._spinalConfig.transformationPhases.size
    val sim = SpinalWavesSim(config, launchViewer = false).compile(new ReviewWavePath)
    assert(config._spinalConfig.transformationPhases.size == phases)
    assert(config._workspaceName == null)
    assert(config._testPath.endsWith("/$TEST"))
    for ((allocated, value) <- Seq("repeat" -> 7, "repeat_1" -> 13)) {
      sim.doSim("repeat", 73) { dut =>
        dut.io.input #= value
        sleep(10)
        assert(dut.io.output.toInt == value + 1)
      }
      val expected = external.resolve(allocated).resolve(s"capture_${allocated}_wave.vcd")
      assert(sim.vcdFile == expected)
      assert(!sim.vcdFile.startsWith(sim.workspace.toAbsolutePath.normalize))
      verify(sim)
      val decoy = sim.workspace.resolve("unrelated.vcd")
      Files.writeString(decoy, "$enddefinitions $end\n")
      Files.setLastModifiedTime(decoy, FileTime.fromMillis(System.currentTimeMillis() + 3600000L))
    }
  }
}
