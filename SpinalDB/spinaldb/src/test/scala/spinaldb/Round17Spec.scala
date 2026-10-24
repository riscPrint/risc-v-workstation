package spinaldb

import java.nio.file.Files
import java.sql.DriverManager
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class Round17Spec extends AnyFunSuite {
  test("round 17: identity audit enumerates every extractor object entry point") {
    import spinal.core.internals._
    // Semantic values use exact class plus origin. Tags and attributes have reflected fallbacks.
    val entries: Seq[(String, Class[_])] = Seq(
      "signal declaration" -> classOf[Bool], "expression reference" -> classOf[Bool],
      "generated signal" -> classOf[Bool], "component" -> classOf[Component], "area" -> classOf[Area],
      "clock domain" -> classOf[ClockDomain], "memory" -> classOf[Mem[_]], "blackbox" -> classOf[BlackBox],
      "tag" -> classOf[ExternalDriverTag], "attribute" -> classOf[AttributeString],
      "literal" -> classOf[BoolLiteral], "enum" -> classOf[SpinalEnumCraft[_]],
      "bundle" -> classOf[Bundle], "Vec" -> classOf[Vec[_]])
    for ((entry, original) <- entries) {
      assert(LibraryClasses.exact(original, original), entry)
      val stream = original.getResourceAsStream("/" + original.getName.replace('.', '/') + ".class")
      val bytes = try stream.readAllBytes() finally stream.close()
      val loader = new ClassLoader(original.getClassLoader) {
        def copyClass(): Class[_] = defineClass(original.getName, bytes, 0, bytes.length, original.getProtectionDomain)
      }
      val copy = loader.copyClass()
      assert(!LibraryClasses.exact(copy, original), entry)
      assert(!LibraryClasses.isSpinal(copy), entry)
    }
    class FieldlessBool extends Bool { override def hasInit: Boolean = false }
    assert(!LibraryClasses.signal(classOf[FieldlessBool]))
    assert(!LibraryClasses.signal(classOf[Round17ResetBool]))
    assert(LibraryClasses.signal(classOf[Bool]))

  }
  test("round 17: signal subclasses are incomplete in declarations, references and generated registers") {
    val root = Files.createTempDirectory("spinaldb-r17").toFile
    Round17Fixtures.main(Array(root.getPath))
    val withReset = Files.readString(root.toPath.resolve("rtl-r17_reset0_named/Round17Reset.v"))
    val withoutReset = Files.readString(root.toPath.resolve("rtl-r17_reset1_named/Round17Reset.v"))
    assert(withReset.contains("posedge clk or posedge reset"))
    assert(!withoutReset.contains("posedge clk or posedge reset"))
    for (container <- 0 to 0) {
      val con = DriverManager.getConnection("jdbc:sqlite:" + new java.io.File(root, s"r17_unused$container.db"))
      try {
        val r = con.createStatement().executeQuery("SELECT key FROM statements WHERE kind='declaration'")
        assert(r.next() && ExprText.isIncomplete(r.getString(1)))
      } finally con.close()
    }
    for (mode <- 0 to 1; kind <- Seq("gen", "named")) {
      val con = DriverManager.getConnection("jdbc:sqlite:" + new java.io.File(root, s"r17_reset${mode}_$kind.db"))
      try {
        val q = con.createStatement()
        val sig = q.executeQuery("SELECT type FROM signals WHERE path = '" + (if (kind == "gen") "_zz_custom" else "r") + "'")
        assert(sig.next() && ExprText.isIncomplete(sig.getString(1)))
        val ref = q.executeQuery("SELECT key FROM assignments a JOIN signals s ON s.id=a.target_id WHERE s.path='y'")
        assert(ref.next() && ExprText.isIncomplete(ref.getString(1)))
      } finally con.close()
    }
  }
}
