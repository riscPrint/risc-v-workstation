package spinalblocks

import java.nio.file.Files

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinalblocks.examples.GcdCluster

class ExtractorSpec extends AnyFunSuite {
  private lazy val design: ujson.Value = {
    val dir = Files.createTempDirectory("spinalblocks-test")
    val out = dir.resolve("demo.json").toFile
    SpinalBlocks.generate(SpinalConfig(targetDirectory = dir.toString), out)(new GcdCluster)
    ujson.read(Files.readString(out.toPath))
  }
  private def module(name: String) = design("modules")(name)
  private def nodes(m: ujson.Value) = m("nodes").arr.map(n => n("id").str -> n).toMap
  private def ep(e: ujson.Value): String = e("kind").str match {
    case "port" => "port:" + e("port").str
    case "inst" => e("id").str + "." + e("port").str
    case "node" => e("id").str
  }
  private def driversOf(m: ujson.Value, sink: String): Set[String] =
    m("nets").arr.filter(_("to").arr.exists(ep(_) == sink)).map(n => ep(n("from"))).toSet

  test("one diagram per Verilog module, with instance counts") {
    assert(design("top").str == "GcdCluster")
    assert(design("modules").obj.keySet == Set("GcdCluster", "StreamFifo", "Gcd"))
    assert(module("Gcd")("instanceCount").num == 2)
  }

  test("registers become nodes and when temporaries fold into control nets") {
    val gcd = module("Gcd")
    assert(nodes(gcd).keySet == Set("sig:x", "sig:y"))
    assert(nodes(gcd).values.forall(_("kind").str == "reg"))
    val load = gcd("nets").arr.find(_("name").str == "io_load").get
    assert(load("control").bool)
    assert(load("to").arr.map(ep).toSet == Set("sig:x", "sig:y"))
    assert(driversOf(gcd, "port:io_result") == Set("sig:x"))
  }

  test("areas nest, keep their class and contain their memories") {
    val top = nodes(module("GcdCluster"))
    assert(top("area:ctrl")("compound").bool)
    assert(top("area:ctrl_fsm")("parent").str == "area:ctrl")
    assert(top("area:ctrl_fsm")("className").str == "spinal.lib.fsm.StateMachine")
    assert(top("area:ctrl/logic")("kind").str == "logic")
    assert(top("area:results")("signals").arr.exists(_("type").str.startsWith("Mem[")))
    // An async read port is drawn as memory -> port; its address feeds the memory node.
    assert(driversOf(module("GcdCluster"), "port:io_rdData") == Set("area:results"))
    assert(driversOf(module("GcdCluster"), "area:results").contains("port:io_rdAddr"))
  }

  test("instances connect port to port and carry their instantiation line") {
    val m = module("GcdCluster")
    assert(driversOf(m, "inst:units_0.io_a") == Set("inst:fifo.io_pop_payload_0"))
    assert(driversOf(m, "inst:fifo.io_push_valid") == Set("port:io_cmd_valid"))
    val unit = m("instances").arr.find(_("name").str == "units_0").get
    val src = Files.readAllLines(java.nio.file.Paths.get(unit("loc")("file").str))
    assert(src.get(unit("loc")("line").num.toInt - 1).contains("new Gcd"))
    assert(module("Gcd")("loc")("line").num.toInt < unit("loc")("line").num.toInt)
    val clk = m("nets").arr.find(_("name").str == "clk").get
    assert(clk("clock").bool)
  }

  test("every endpoint exists and no net loops onto its driver") {
    for ((_, m) <- design("modules").obj) {
      val ports = m("ports").arr.map("port:" + _("name").str).toSet
      val insts = m("instances").arr.map(i => i("id").str -> design("modules")(i("module").str)("ports").arr.map(_("name").str).toSet).toMap
      val ids = nodes(m)
      def valid(e: ujson.Value): Boolean = e("kind").str match {
        case "port" => ports.contains("port:" + e("port").str)
        case "inst" => insts.get(e("id").str).exists(_.contains(e("port").str))
        case "node" => ids.get(e("id").str).exists(!_("compound").bool)
      }
      for (n <- m("nets").arr) {
        assert(valid(n("from")), n)
        assert(n("to").arr.forall(valid), n)
        assert(!n("to").arr.map(ep).contains(ep(n("from"))), n)
      }
    }
  }

  test("state machines: StateMachine and plain enum registers") {
    val fsms = module("GcdCluster")("fsms").arr.map(f => f("name").str -> f).toMap
    val sm = fsms("ctrl_fsm")
    assert(sm("kind").str == "statemachine")
    assert(sm("reset").str == "idle")
    assert(sm("states").arr.map(_("name").str) == Seq("idle", "run", "done")) // BOOT hidden
    def edges(f: ujson.Value) = f("transitions").arr.map(t => (t("from").strOpt, t("to").strOpt, t("condition").strOpt)).toSet
    assert(edges(sm) == Set(
      (Some("idle"), Some("run"), Some("fifo.io_pop_valid")),
      (Some("run"), Some("done"), Some("units_0.io_valid && units_1.io_valid")),
      (Some("done"), Some("idle"), None)))
    assert(sm("transitions").arr.exists(_("comment").strOpt.contains("ready for the next command")))
    val phase = fsms("results_phase")
    assert(phase("kind").str == "enum" && phase("reset").str == "Empty")
    assert(edges(phase).map(e => (e._1, e._2)) == Set(Some("Empty") -> Some("Filling"), Some("Filling") -> Some("Full"), Some("Full") -> Some("Empty")))
    assert(phase("node").str == "area:results")
  }
}
