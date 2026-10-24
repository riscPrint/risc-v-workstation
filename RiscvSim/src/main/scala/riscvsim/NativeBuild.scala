package riscvsim

import java.io.File
import java.nio.channels.FileChannel
import java.nio.file.{Files, Paths, StandardOpenOption}
import java.nio.file.attribute.BasicFileAttributes
import java.util.concurrent.TimeUnit
import org.apache.commons.io.FileUtils
import scala.util.Try

/** One native identity per JVM, supplied by the launcher. Direct JVM launches stay inconclusive. */
object NativeBuild {
  lazy val current: ujson.Obj = sys.props.get("riscvsim.native.identity")
    .flatMap(s => Try(ujson.Obj.from(ujson.read(s).obj)).toOption).getOrElse(
      ujson.Obj("cache_enabled" -> false,
        "cache_disabled_reasons" -> ujson.Arr("native build identity unavailable"), "environment" -> ujson.Obj()))

  /** The launcher installs the private PATH before it starts this JVM. */
  lazy val pinned: Boolean = sys.props.get("riscvsim.native.bin").exists { bin =>
    sys.env.get("RISCVSIM_PINNED_BIN").contains(bin) &&
      sys.env.get("PATH").exists(_.split(File.pathSeparator).headOption.contains(bin))
  }

  private lazy val identityProblem: Option[String] = Try {
    if (!pinned) Some("input_not_captured:native_lookup")
    else if (!current("cache_enabled").bool) Some("input_not_captured:native_build")
    else {
      require(current("cache_disabled_reasons").arr.isEmpty)
      require(current("namespace").str.matches("[A-Za-z0-9_-]+"))
      require(current("sha256").str.matches("[0-9a-f]{64}"))
      val files = current("files").arr.map(f => f("path").str -> f("sha256").str).toMap
      val tools = current("tools").obj
      for (name <- Seq("python", "java", "verilator", "compiler", "linker", "make", "ar", "sh", "bash", "perl")) {
        val tool = tools(name)
        require(tool("version").str.nonEmpty && files.get(tool("path").str).contains(tool("sha256").str))
      }
      for (name <- Seq("make_wrapper", "verilated_mk"))
        require(files.get(current(s"${name}_path").str).contains(current(s"${name}_sha256").str))
      None
    }
  }.getOrElse(Some("input_not_captured:tool_identity"))

  /** Check once before each native receipt or C1 publication. Tools stay stable under C8. */
  def problem: Option[String] = identityProblem.orElse {
    Try {
      current("files").arr.find { item =>
        val info = Files.readAttributes(Paths.get(item("path").str), classOf[BasicFileAttributes])
        !info.isRegularFile || info.size().toString != item("size").str ||
          info.lastModifiedTime().to(TimeUnit.NANOSECONDS).toString != item("modified_ns").str
      }.map(item => s"input_not_captured:tool:${item("path").str}")
    }.getOrElse(Some("input_not_captured:tool_identity"))
  }

  private val activeCache = new ThreadLocal[File]()

  private def namespace(cache: File): File = new File(cache, s"${current("namespace").str}/${current("sha256").str}")
  private def receipt(directory: File): File = new File(directory, ".riscvsim-verified")
  private def verified(directory: File): Boolean = Try {
    Files.readString(receipt(directory).toPath) == current("sha256").str
  }.getOrElse(false)
  private def entries(directory: File): Seq[File] = Option(directory.listFiles()).toSeq.flatten.filter(_.isDirectory).toSeq

  private val cacheMutex = new Object
  private def locked[T](directory: File)(body: => T): T = cacheMutex.synchronized {
    directory.mkdirs()
    val channel = FileChannel.open(new File(directory.getParentFile, directory.getName + ".lock").toPath,
      StandardOpenOption.CREATE, StandardOpenOption.WRITE)
    try {
      val lock = channel.lock()
      try body finally lock.release()
    } finally channel.close()
  }

  /** A killed or unverified build cannot leave a reusable cache entry. */
  def transaction[T](cache: File, valid: => Boolean)(body: => T): T = {
    if (identityProblem.nonEmpty) return body
    val directory = namespace(cache)
    locked(directory) {
      // Spinal may have written an entry before a previous process stopped.
      entries(directory).filterNot(verified).foreach(FileUtils.deleteDirectory)
      activeCache.set(directory)
      try {
        val result = body
        if (valid) {
          entries(directory).filterNot(verified).foreach { entry =>
            Files.writeString(receipt(entry).toPath, current("sha256").str)
          }
        }
        result
      } finally {
        entries(directory).filterNot(verified).foreach(FileUtils.deleteDirectory)
        activeCache.remove()
      }
    }
  }

  def cachePath(cache: File): Option[File] =
    Option(activeCache.get()).filter(_.getAbsoluteFile == namespace(cache).getAbsoluteFile)

  private def replayEnvironment = current("environment").obj.toSeq.sortBy(_._1)
    .filterNot(_._1 == "SPINAL_MAKE_CMD") // the current checkout supplies its own wrapper

  /** Keep value assignments as shell prefixes, which the debug adapter parser preserves. */
  def replayEnv: Seq[(String, String)] =
    replayEnvironment.collect { case (k, v) if v != ujson.Null => k -> v.str }

  /** Restore absence too. Other environment values stay local; their digest is in provenance. */
  def replayArgs: Seq[String] =
    Seq("env") ++ replayEnvironment.collect { case (k, ujson.Null) => Seq("-u", k) }.flatten
}
