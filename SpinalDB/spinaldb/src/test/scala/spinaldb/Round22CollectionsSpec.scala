package spinaldb

import java.nio.file.{Files, Paths}
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.internals._
import scala.collection.immutable

class Round22CollectionPhase(val payload: Any) extends PhaseNetlist {
  override def impl(pc: PhaseContext): Unit = ()
}
class Round22UserSeq extends immutable.AbstractSeq[Any] {
  override def length: Int = throw new AssertionError("user length called")
  override def apply(n: Int): Any = throw new AssertionError("user apply called")
  override def iterator: Iterator[Any] = throw new AssertionError("user iterator called")
}
class Round22CollectionCycle(var payload: Any)

class Round22CollectionsSpec extends AnyFunSuite {
  private def key(payload: Any): String = {
    val config = SpinalConfig(targetDirectory = Files.createTempDirectory("spinaldb-r22collections").toString)
    config.transformationPhases += new Round22CollectionPhase(payload)
    EmissionConfig.key(SpinalDB.elaborate(config, traceNaming = false)(new Round22Top))
  }
  private def complete(payload: Any): String = {
    val k = key(payload)
    assert(!ExprText.isIncomplete(k), k)
    k
  }

  test("round 22: unchanged immutable List phase has a complete stable key") {
    assert(complete(List("y")) == complete(List("y")))
    assert(complete(List("y")) != complete(List("z")))
    assert(complete(List("y", "z")) != complete(List("z", "y")))
  }
  test("round 22: strict immutable sequences, Option and tuples retain nested supported values") {
    val values: List[Any] = List(Nil, Vector.empty, Vector("y", "z"), Vector.range(0, 1050),
      immutable.Seq("y"), immutable.Queue("y", "z"), immutable.ArraySeq("y", "z"), 0 until 3,
      None, Some(("y", List(1, 2))), Tuple1("y"), (1, 2), ("y", true, Vector(3)))
    assert(complete(values) == complete(values))
    assert(complete(Some(("y", 1))) != complete(Some(("y", 2))))
    assert(complete(None) != complete(Some(null)))
    assert(complete(List("y")) != complete(Vector("y")))
    assert(complete(Vector("y", "z")) != complete(Vector("z", "y")))
    assert(complete(("y", "z")) != complete(("z", "y")))
  }
  test("round 22: Range bounds and step remain part of the key even when elements are equal") {
    assert(complete(0 until 0) != complete(1 until 1))
    assert(complete(0 until 1 by 1) != complete(0 until 1 by 2))
  }
  test("round 22: immutable sets and maps retain iteration order and values") {
    val values: List[Any] = (0 to 6).toList.flatMap { n =>
      List(immutable.Set.from(0 until n), immutable.Map.from((0 until n).map(i => i -> s"v$i")))
    } ::: List(immutable.ListSet("y", "z"), immutable.ListMap("y" -> 1, "z" -> 2),
      immutable.VectorMap("y" -> 1, "z" -> 2), immutable.BitSet(1, 70),
      immutable.TreeSet(1, 2), immutable.TreeMap(1 -> "y", 2 -> "z"))
    assert(complete(values) == complete(values))
    assert(complete(immutable.ListSet("y", "z")) != complete(immutable.ListSet("z", "y")))
    assert(complete(immutable.ListMap("y" -> 1, "z" -> 2)) !=
      complete(immutable.ListMap("z" -> 2, "y" -> 1)))
    assert(complete(immutable.VectorMap("y" -> 1)) != complete(immutable.VectorMap("y" -> 2)))
    assert(complete(immutable.TreeSet.empty[Int]) != complete(immutable.TreeSet.empty[Int](Ordering.Int.reverse)))
  }
  test("round 22: user collection subclasses remain incomplete without invoking their iterator") {
    assert(ExprText.isIncomplete(key(new Round22UserSeq)))
  }
  test("round 22: nested unsupported values and cycles remain incomplete") {
    assert(ExprText.isIncomplete(key(Some(List(new java.io.File("unsupported"))))))
    val cycle = new Round22CollectionCycle(null)
    cycle.payload = List(Some(cycle))
    assert(ExprText.isIncomplete(key(cycle)))
  }
  test("round 22: lazy sequences and maps with defaults remain incomplete") {
    val lazyValues = immutable.LazyList.continually(throw new AssertionError("lazy value evaluated"))
    assert(ExprText.isIncomplete(key(lazyValues)))
    val map = immutable.Map("y" -> 1).withDefault(_ => throw new AssertionError("map default called"))
    assert(ExprText.isIncomplete(key(map)))
  }
}

object Round22CollectionFixtures {
  def main(args: Array[String]): Unit = {
    val root = Paths.get(args(0))
    for ((name, payload) <- Seq("list0" -> List("y"), "list1" -> List("y"),
      "changed" -> List("z"), "subclass" -> new Round22UserSeq)) {
      val dir = root.resolve(name); Files.createDirectories(dir)
      val config = SpinalConfig(targetDirectory = dir.resolve("rtl").toString)
      config.transformationPhases += new Round22CollectionPhase(payload)
      SpinalDB.generate(config, dir.resolve("design.db").toFile,
        DbOptions(pdg = false, blocks = false, hgldd = false, sourceRoots = Nil))(new Round22Top)
    }
  }
}
