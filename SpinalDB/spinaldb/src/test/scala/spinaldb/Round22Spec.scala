package spinaldb

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.internals._
import scala.collection.mutable.ArrayBuffer

object Round22Callback {
  def add(phases: ArrayBuffer[Phase]): Unit = phases.insert(0, new Round22Phase(1))
  def config(dir: String): SpinalConfig = {
    val c = SpinalConfig(targetDirectory = dir)
    c.phasesInserters += (add _)
    c
  }
}
class Round22Phase(val setting: Int) extends PhaseNetlist {
  override def impl(pc: PhaseContext): Unit = ()
  override def toString: String = throw new AssertionError("user toString called")
}
class Round22Top extends Component { val y = out Bool(); y := True }

class Round22Spec extends AnyFunSuite {
  test("round 22: unchanged user phase callback has a complete stable emission key") {
    def key(): String = {
      val c = Round22Callback.config(Files.createTempDirectory("spinaldb-r22").toString)
      EmissionConfig.key(SpinalDB.elaborate(c, traceNaming = false)(new Round22Top))
    }
    val a = key(); val b = key()
    assert(!ExprText.isIncomplete(a), a)
    assert(a == b)
  }
}

class Round22Payload(val setting: Int) {
  override def toString: String = throw new AssertionError("user toString called")
  private def writeReplace(): AnyRef = throw new AssertionError("user serialization called")
}
class Round22Cycle(val items: ArrayBuffer[Any])
class Round22Ordered(val items: scala.collection.mutable.LinkedHashMap[String, Int])
class Round22MoreSpec extends AnyFunSuite {
  def emitted(config: SpinalConfig): String =
    EmissionConfig.key(SpinalDB.elaborate(config, traceNaming = false)(new Round22Top))
  def config(): SpinalConfig = SpinalConfig(targetDirectory = Files.createTempDirectory("spinaldb-r22").toString)

  test("round 22: reflected phase state and other user payload state are keyed without user methods") {
    def key(n: Int, kind: String): String = {
      val c = config()
      kind match {
        case "phase" => c.transformationPhases += new Round22Phase(n)
        case "payload" => c.flags += new Round22Payload(n)
        case "callback" => c.phasesInserters += ((phases: ArrayBuffer[Phase]) => phases.insert(0, new Round22Phase(n)))
      }
      emitted(c)
    }
    for (kind <- Seq("phase", "payload", "callback")) {
      val a = key(1, kind); val b = key(2, kind)
      assert(!ExprText.isIncomplete(a), a)
      assert(a != b, kind)
      assert(a == key(1, kind), kind)
    }
  }
  test("round 22: directory and jar captures include changed helper code with the same phase class name") {
    for (jar <- Seq(false, true)) {
      val root = Files.createTempDirectory("spinaldb-r22code")
      val a = Round22Fixtures.phase(root.resolve("a"), 0, jar = jar)
      val b = Round22Fixtures.phase(root.resolve("b"), 1, jar = jar)
      val capture = new CodeCapture
      assert(a.getClass.getName == b.getClass.getName)
      assert(capture.classKey(a.getClass) != capture.classKey(b.getClass))
    }
  }
  test("round 22: missing compiled phase bytes stay incomplete") {
    val root = Files.createTempDirectory("spinaldb-r22missing")
    val c = config()
    c.transformationPhases += Round22Fixtures.phase(root, 0, unreadable = true)
    assert(ExprText.isIncomplete(emitted(c)))
  }
  test("round 22: an ordinary class without a code source stays incomplete") {
    val name = classOf[Round22Phase].getName
    val stream = getClass.getResourceAsStream("/" + name.replace('.', '/') + ".class")
    val bytes = try stream.readAllBytes() finally stream.close()
    val loader = new ClassLoader(getClass.getClassLoader) {
      def make(): Class[_] = defineClass(name, bytes, 0, bytes.length)
    }
    val phase = loader.make().getConstructor(classOf[Int]).newInstance(Int.box(1)).asInstanceOf[Phase]
    val c = config(); c.transformationPhases += phase
    assert(ExprText.isIncomplete(emitted(c)))
  }
  test("round 22: ordered user maps retain their insertion order") {
    def key(reverse: Boolean): String = {
      val c = config()
      val items = Seq("first" -> 1, "second" -> 2)
      val map = scala.collection.mutable.LinkedHashMap((if (reverse) items.reverse else items): _*)
      c.flags += new Round22Ordered(map)
      emitted(c)
    }
    val a = key(false); val b = key(true)
    assert(!ExprText.isIncomplete(a), a)
    assert(a != b)
  }
  test("round 22: cyclic user collections remain incomplete") {
    val c = config()
    val cycle = ArrayBuffer[Any]()
    cycle += cycle
    c.flags += new Round22Cycle(cycle)
    assert(ExprText.isIncomplete(emitted(c)))
  }
  test("round 22: new code sources cannot be captured after elaboration starts") {
    val root = Files.createTempDirectory("spinaldb-r22late")
    val p = Round22Fixtures.phase(root, 0)
    val capture = new CodeCapture
    capture.seal()
    intercept[IllegalArgumentException] { capture.classKey(p.getClass) }
  }
  test("round 22: a persistent classpath edit invalidates the capture") {
    val root = Files.createTempDirectory("spinaldb-r22edit")
    val p = Round22Fixtures.phase(root, 0)
    val capture = new CodeCapture
    capture.classKey(p.getClass)
    assert(capture.unchanged)
    Files.write(root.resolve("r22/Helper.class"), Array[Byte](0))
    assert(!capture.unchanged)
  }
}
