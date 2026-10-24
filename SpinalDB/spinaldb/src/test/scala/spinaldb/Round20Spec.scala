package spinaldb

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class Round20Spec extends AnyFunSuite {
  test("all port directions keep external identity before temporary expansion") {
    val directory = Files.createTempDirectory("spinaldb-port-identity-")
    val report = SpinalDB.elaborate(SpinalConfig(targetDirectory = directory.toString), traceNaming = false)(new Component {
      val a, b = in Bool()
      val x, y = out Bool()
      val p, q = inout(Analog(Bool()))
      a.setName("_zz_a"); b.setName("_zz_b")
      x.setName("_zz_x"); y.setName("_zz_y")
      p.setName("_zz_p"); q.setName("_zz_q")
      x := a; y := b
    })
    val top = report.toplevel
    // Force the generated predicate true: port identity must take priority over it.
    val text = new ExprText((bt, _) => bt.getName(), _ => true)
    for ((left, right) <- Seq((top.a, top.b), (top.x, top.y), (top.p, top.q))) {
      val keys = Seq(text.key(left, top), text.key(right, top))
      assert(keys.distinct.size == 2, keys)
      assert(keys.head.contains(left.getName()) && keys.last.contains(right.getName()), keys)
      assert(!keys.exists(k => k.contains("$gen:") || ExprText.isIncomplete(k)), keys)
    }
  }

  test("explicit default path strings are required roots") {
    assert(DbOptions().sourceRoots eq DbOptions.DefaultSourceRoots)
    val explicit = Main.parse(Seq("--source-root", "src/main/scala", "--source-root", "src/test/scala"))._1
    assert(explicit.sourceRoots == DbOptions.DefaultSourceRoots)
    assert(!(explicit.sourceRoots eq DbOptions.DefaultSourceRoots))
    assert(!(DbOptions(sourceRoots = spinalwaves.SourceLocator.defaultRoots).sourceRoots eq DbOptions.DefaultSourceRoots))
  }
}
