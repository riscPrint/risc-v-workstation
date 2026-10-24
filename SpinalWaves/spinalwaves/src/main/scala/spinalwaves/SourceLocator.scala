package spinalwaves

import java.nio.file.{Files, Path, Paths}
import scala.jdk.CollectionConverters._
import spinal.core.ScalaLocated

final case class SourceLocation(absPath: String, line: Int, col: Int = 1)

/** Resolves Spinal's first retained Scala stack frame against explicit source roots. */
object SourceLocator {
  def defaultRoots: Seq[Path] = Seq(Paths.get("src/main/scala"), Paths.get("src/test/scala"))

  def fromFrame(frame: StackTraceElement, sourceRoots: Seq[Path] = defaultRoots): SourceLocation = {
    val file = Option(frame.getFileName).getOrElse("unknown")
    val direct = Paths.get(file)
    val resolved = if (direct.isAbsolute) Some(direct) else {
      val candidates = sourceRoots.flatMap(root => index(root).getOrElse(file, Vector.empty))
      // Prefer the file whose directory matches the frame's package (same file name in several packages).
      val pkgDir = Option(frame.getClassName).filter(_.contains('.'))
        .map(c => c.substring(0, c.lastIndexOf('.')).replace('.', '/'))
      pkgDir.flatMap(d => candidates.find(_.getParent.toString.replace('\\', '/').endsWith(d)))
        .orElse(candidates.headOption)
    }
    SourceLocation(resolved.map(_.toAbsolutePath.normalize.toString).getOrElse(file), frame.getLineNumber, 1)
  }

  private val indexCache = scala.collection.concurrent.TrieMap.empty[Path, Map[String, Vector[Path]]]

  /** File name -> files under `root`, sorted; walked once per root. */
  private def index(root: Path): Map[String, Vector[Path]] =
    indexCache.getOrElseUpdate(root.toAbsolutePath.normalize, {
      if (!Files.isDirectory(root)) Map.empty
      else {
        val stream = Files.walk(root)
        try stream.iterator().asScala.filter(Files.isRegularFile(_)).toVector.sortBy(_.toString)
          .groupBy(_.getFileName.toString)
        finally stream.close()
      }
    })

  /** Frames Spinal's filter keeps that are never user source: JVM reflection/method handles, and the
    * SpinalWaves/SpinalTrace entry points (they create the toplevel's default clock domain). */
  private def isJvmInternal(f: StackTraceElement): Boolean = {
    val c = f.getClassName
    c.startsWith("java.") || c.startsWith("jdk.") || c.startsWith("sun.") || c.startsWith("javax.") ||
      c.startsWith("spinalwaves.SpinalWaves") || c.startsWith("spinaltrace.SpinalTrace")
  }

  def locate(value: ScalaLocated, sourceRoots: Seq[Path] = defaultRoots): Option[SourceLocation] =
    Option(value.scalaTrace).flatMap(t => ScalaLocated.filterStackTrace(t.getStackTrace)
      .find(f => f.getFileName != null && f.getLineNumber > 0 && !isJvmInternal(f))).map(fromFrame(_, sourceRoots))

  def apply(value: ScalaLocated, sourceRoots: Seq[Path] = defaultRoots): Option[SourceLocation] = locate(value, sourceRoots)
}
