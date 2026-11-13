package spinaldb

import java.net.URLClassLoader
import java.nio.file.{Files, Path, Paths}
import java.util.jar.{JarEntry, JarOutputStream}
import javax.tools.ToolProvider
import spinal.core._
import spinal.core.internals._
import scala.jdk.CollectionConverters._

/** Compile the same phase name with changed helper code. Never edit an existing classpath. */
object Round22Fixtures {
  def phase(root: Path, setting: Int, jar: Boolean = false, unreadable: Boolean = false): Phase = {
    Files.createDirectories(root.resolve("r22"))
    val src = root.resolve("r22/UserPhase.java")
    Files.writeString(src, """package r22;
      public class UserPhase implements spinal.core.internals.Phase {
        public boolean hasNetlistImpact() { return true; }
        public void impl(spinal.core.internals.PhaseContext pc) {
          pc.topLevel().rework(() -> {
            scala.collection.Iterator<spinal.core.BaseType> ports = pc.topLevel().getAllIo().iterator();
            while (ports.hasNext()) {
              spinal.core.BaseType y = ports.next();
              if (y.isOutput()) {
                y.removeAssignments(true, true, true);
                y.assignFromBits((spinal.core.Bits) spinal.core.B$.MODULE$.apply(
                  y.getBitsWidth() + "'b" + (Helper.value() ? "1" : "0")));
              }
            }
            return scala.runtime.BoxedUnit.UNIT;
          });
        }
      }
      class Helper { static boolean value() { return SETTING; } }
      """.replace("SETTING", (setting == 1).toString))
    val compiler = ToolProvider.getSystemJavaCompiler
    require(compiler != null, "round 22 tests need a JDK")
    require(compiler.run(null, null, null, "-cp", sys.props("java.class.path"), "-d", root.toString,
      src.toString) == 0, "phase fixture compilation failed")
    Files.delete(src)
    val entry = if (jar) {
      val out = root.resolve("phase.jar")
      val zip = new JarOutputStream(Files.newOutputStream(out))
      try for (name <- Seq("r22/UserPhase.class", "r22/Helper.class")) {
        zip.putNextEntry(new JarEntry(name)); zip.write(Files.readAllBytes(root.resolve(name))); zip.closeEntry()
      } finally zip.close()
      out
    } else root
    val loader = new URLClassLoader(Array(entry.toUri.toURL), getClass.getClassLoader)
    try {
      val result = Class.forName("r22.UserPhase", true, loader).getConstructor().newInstance().asInstanceOf[Phase]
      // Resolve Helper before removing the class bytes. Execution still works; identity must refuse.
      Class.forName("r22.Helper", true, loader)
      if (unreadable) Files.delete(root.resolve("r22/UserPhase.class"))
      result
    } finally loader.close()
  }
  def write(root: Path, name: String, phase: Option[Phase] = None, callback: Boolean = false): Path = {
    val dir = root.resolve(name); Files.createDirectories(dir)
    val config = if (callback) Round22Callback.config(dir.resolve("rtl").toString)
      else SpinalConfig(targetDirectory = dir.resolve("rtl").toString)
    phase.foreach(config.transformationPhases += _)
    val out = dir.resolve("design.db")
    SpinalDB.generate(config, out.toFile, DbOptions(pdg = false, blocks = false, hgldd = false, sourceRoots = Nil))(
      new Round22Poison)
    out
  }
  def main(args: Array[String]): Unit = {
    val root = Paths.get(args(0))
    for (n <- 0 to 1) write(root, s"callback$n", callback = true)
    for (n <- 0 to 1) write(root, s"code$n", Some(phase(root.resolve(s"classes$n"), n)))
    write(root, "unreadable", Some(phase(root.resolve("missing"), 0, unreadable = true)))
  }
}
class Round22Poison extends Component { val y = out Bits(4 bits); y.assignDontCare() }
