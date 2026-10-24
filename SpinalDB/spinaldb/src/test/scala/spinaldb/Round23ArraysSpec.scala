package spinaldb

import java.nio.file.{Files, Paths}
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.internals._

class Round23ArrayPhase(val names: Array[String]) extends PhaseNetlist {
  override def impl(pc: PhaseContext): Unit = pc.walkStatements {
    case s: BaseType if s.isOutput && names.contains(s.getName()) => s.addAttribute("keep")
    case _ =>
  }
}

class Round23ArraysSpec extends AnyFunSuite {
  private def key(payload: Any): String = {
    val config = SpinalConfig(targetDirectory = Files.createTempDirectory("spinaldb-r23arrays").toString)
    config.transformationPhases += new Round22CollectionPhase(payload)
    EmissionConfig.key(SpinalDB.elaborate(config, traceNaming = false)(new Round22Top))
  }
  private def complete(payload: Any): String = {
    val k = key(payload)
    assert(!ExprText.isIncomplete(k), k)
    k
  }
  test("round 23: array phase state has stable complete keys and detects value and order changes") {
    assert(complete(Array("y")) == complete(Array("y")))
    assert(complete(Array("y")) != complete(Array("z")))
    assert(complete(Array("y", "z")) != complete(Array("z", "y")))
  }
  test("round 23: primitive, reference and nested arrays retain component type") {
    val payload = Array[Any](Array(true, false), Array[Byte](1, 2), Array[Short](1, 2),
      Array(1, 2), Array(1L, 2L), Array(1.0f, 2.0f), Array(1.0, 2.0), Array('y', 'z'),
      Array(Array("y")), Array[AnyRef](List("y"), null), Array(BigInt(1), BigInt(2)))
    assert(complete(payload) == complete(payload))
    assert(complete(Array.empty[Int]) != complete(Array.empty[Long]))
    assert(complete(Array[AnyRef]("y")) != complete(Array("y")))
    assert(complete(Array(1, 2)) != complete(Array(1, 3)))
    assert(complete(Array("y")) != complete(List("y")))
  }
  test("round 23: arrays preserve incomplete values and cycle markers") {
    assert(ExprText.isIncomplete(key(Array(new java.io.File("unsupported")))))
    val cycle = new Array[AnyRef](1)
    cycle(0) = cycle
    assert(ExprText.isIncomplete(key(cycle)))
    assert(ExprText.isIncomplete(key(Array(new Round22UserSeq))))
  }
}

object Round23ArrayFixtures {
  def main(args: Array[String]): Unit = {
    val root = Paths.get(args(0))
    for ((name, names) <- Seq("array0" -> Array("y"), "array1" -> Array("y"),
      "changed" -> Array("z"))) {
      val dir = root.resolve(name); Files.createDirectories(dir)
      val config = SpinalConfig(targetDirectory = dir.resolve("rtl").toString)
      config.transformationPhases += new Round23ArrayPhase(names)
      SpinalDB.generate(config, dir.resolve("design.db").toFile,
        DbOptions(pdg = false, blocks = false, hgldd = false, sourceRoots = Nil))(new Round22Top)
    }
  }
}
