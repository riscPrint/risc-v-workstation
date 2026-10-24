package spinaldb

import java.io.ByteArrayInputStream
import java.lang.invoke.SerializedLambda
import java.lang.reflect.Modifier
import java.nio.file.{Files, Path, Paths}
import java.nio.file.attribute.BasicFileAttributes
import java.security.MessageDigest
import java.util.zip.ZipInputStream
import scala.collection.mutable
import scala.jdk.CollectionConverters._
import scala.tools.asm.ClassReader
import scala.util.control.NonFatal

/** Per-elaboration private copies of the compiled classpath. Keys use only these bytes.
  * Whole entries include helper classes and resources, even helpers outside a phase's package.
  * The ordered classpath also covers dependencies in other entries. Paths are not key material.
  * C8 assumes installed jars and inputs are stable; size/mtime/file-set checks detect normal edits.
  */
private[spinaldb] final class CodeCapture {
  private case class Stamp(size: Long, modified: java.nio.file.attribute.FileTime, directory: Boolean)
  private def stamp(p: Path): Stamp = {
    val a = Files.readAttributes(p, classOf[BasicFileAttributes])
    Stamp(a.size, a.lastModifiedTime, a.isDirectory)
  }
  private def hash(bytes: Array[Byte]): String =
    MessageDigest.getInstance("SHA-256").digest(bytes).map(b => f"${b & 255}%02x").mkString
  private def entries(p: Path): Vector[Path] = {
    val stream = Files.walk(p)
    try stream.iterator.asScala.toVector.sortBy(x => p.relativize(x).toString)
    finally stream.close()
  }
  private case class Entry(path: Path, stamps: Vector[(Path, Stamp)], copies: Map[String, Array[Byte]], key: String) {
    def unchanged: Boolean = try {
      val now = if (Files.isDirectory(path)) entries(path) else Vector(path)
      now == stamps.map(_._1) && stamps.forall { case (p, s) => stamp(p) == s }
    } catch { case NonFatal(_) => false }
    def classBytes(name: String): Array[Byte] = {
      val file = name.replace('.', '/') + ".class"
      if (copies.contains(file)) copies(file)
      else if (copies.contains("<jar>")) {
        val zip = new ZipInputStream(new ByteArrayInputStream(copies("<jar>")))
        try {
          var item = zip.getNextEntry
          while (item != null) {
            if (item.getName == file) return zip.readAllBytes()
            item = zip.getNextEntry
          }
          throw new IllegalArgumentException("class absent from captured jar")
        } finally zip.close()
      } else throw new IllegalArgumentException("class absent from captured directory")
    }
  }
  private val captured = mutable.LinkedHashMap[Path, Entry]()
  private var total: Long = 0
  private var sealedInputs = false
  def seal(): Unit = { sealedInputs = true }
  private def capture(path: Path): Entry = captured.getOrElseUpdate(path, {
    require(!sealedInputs, "compiled classpath entry was not captured before elaboration")
    val paths = if (Files.isDirectory(path)) entries(path) else Vector(path)
    require(paths.forall(p => !Files.isSymbolicLink(p)), "nested classpath symlink is unsupported")
    val stamps = paths.map(p => p -> stamp(p))
    val directory = Files.isDirectory(path)
    val copies = stamps.filterNot(_._2.directory).map { case (p, s) =>
      total += s.size
      require(total <= 512L * 1024 * 1024 && paths.size <= 100000, "compiled classpath capture limit")
      val bytes = Files.readAllBytes(p)
      require(bytes.length == s.size && stamp(p) == s, "compiled classpath changed during capture")
      (if (directory) path.relativize(p).toString.replace('\\', '/') else "<jar>") -> bytes
    }.toMap
    val parts = stamps.map { case (p, s) =>
      val name = if (directory) path.relativize(p).toString.replace('\\', '/') else "<jar>"
      KeyEnc.framed(name) + (if (s.directory) "directory" else hash(copies(name)))
    }.mkString
    Entry(path, stamps, copies, hash(parts.getBytes(java.nio.charset.StandardCharsets.UTF_8)))
  })
  private lazy val classpath: String = {
    val paths = sys.props("java.class.path").split(java.io.File.pathSeparator).toVector
    require(paths.nonEmpty && paths.forall(_.nonEmpty), "missing compiled classpath")
    paths.map(p => capture(Paths.get(p).toRealPath()).key).map(KeyEnc.framed).mkString("classpath[", ",", "]")
  }
  private def source(c: Class[_]): Entry = {
    val url = Option(c.getProtectionDomain).flatMap(d => Option(d.getCodeSource)).map(_.getLocation).get
    require(url.getProtocol == "file", "unsupported compiled class source")
    capture(Paths.get(url.toURI).toRealPath())
  }
  def classKey(c: Class[_]): String = {
    val cp = classpath
    val entry = source(c)
    val bytes = entry.classBytes(c.getName)
    require(new ClassReader(bytes).getClassName == c.getName.replace('.', '/'), "compiled class name mismatch")
    "code(" + KeyEnc.name(c.getName) + ",sha256=" + hash(bytes) + ",entry=" + entry.key +
      ",classpath=" + hash(cp.getBytes(java.nio.charset.StandardCharsets.UTF_8)) + ")"
  }

  /** Hidden LambdaMetafactory classes have no readable .class resource. Only the JVM-generated
    * metadata accessor on a checked hidden synthetic nestmate is used. Never invoke writeReplace
    * on an ordinary user class. The implementation class/method replaces the unstable VM suffix.
    * Captured arguments are read from the final JDK SerializedLambda, not through user methods.
    */
  def lambda(v: AnyRef): Option[(String, Seq[Any])] = {
    val c = v.getClass
    if (!c.isHidden || !c.isSynthetic || !c.getName.startsWith(c.getNestHost.getName + "$$Lambda")) return None
    val host = c.getNestHost
    val hostKey = classKey(host)
    require(c.getProtectionDomain == host.getProtectionDomain, "lambda origin mismatch")
    val method = c.getDeclaredMethod("writeReplace")
    require(Modifier.isPrivate(method.getModifiers) && Modifier.isFinal(method.getModifiers) &&
      method.getReturnType == classOf[Object], "unsupported hidden lambda metadata")
    method.setAccessible(true)
    val sl = method.invoke(v).asInstanceOf[SerializedLambda]
    require(sl.getClass == classOf[SerializedLambda] && sl.getCapturingClass == host.getName.replace('.', '/'),
      "lambda owner mismatch")
    val impl = Class.forName(sl.getImplClass.replace('/', '.'), false, host.getClassLoader)
    val identity = Seq(hostKey, classKey(impl), sl.getImplMethodName, sl.getImplMethodSignature,
      sl.getImplMethodKind.toString, sl.getFunctionalInterfaceClass, sl.getFunctionalInterfaceMethodName,
      sl.getFunctionalInterfaceMethodSignature, sl.getInstantiatedMethodType).map(KeyEnc.framed).mkString("lambda[", ",", "]")
    Some(identity -> (0 until sl.getCapturedArgCount).map(sl.getCapturedArg))
  }

  def unchanged: Boolean = captured.values.forall(_.unchanged)
}
