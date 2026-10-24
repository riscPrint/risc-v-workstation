package spinalkonata.boom

import java.io.File
import java.nio.file.{Files, LinkOption, Path}
import java.nio.file.attribute.BasicFileAttributes
import java.util.concurrent.TimeUnit
import scala.jdk.CollectionConverters._
import riscvsim.ElfFile

/** C8 equivalent for the standalone Scala harness. The ELF parser is shared with RiscvSim. */
private[boom] object InputCapture {
  def hash(bytes: Array[Byte]): String = ElfFile.sha256(bytes)
  def stamp(path: Path): String = {
    val a = Files.readAttributes(path, classOf[BasicFileAttributes], LinkOption.NOFOLLOW_LINKS)
    require(a.isRegularFile, s"input_not_captured:$path: not a regular file")
    // ctime detects edit-and-revert, including metadata changes that restore mtime.
    Seq(a.fileKey(), a.size(), a.lastModifiedTime(), Files.getAttribute(path, "unix:ctime"),
      Files.getAttribute(path, "unix:mode")).mkString(":")
  }
  def resolve(source: Path): (Path, ujson.Arr) = {
    val current = source.toAbsolutePath
    val links = ujson.Arr()
    var count = 0
    // Resolve each lookup component once. Record literal link targets.
    var resolved = current.getRoot
    var pending = current.iterator().asScala.map(_.toString).toList
    while (pending.nonEmpty) {
      val name = pending.head; pending = pending.tail
      if (name == "..") resolved = resolved.getParent
      else if (name != ".") {
        val next = resolved.resolve(name)
        if (Files.isSymbolicLink(next)) {
          count += 1
          require(count <= 40, s"input_not_captured:$source: symlink cycle")
          val target = Files.readSymbolicLink(next)
          links.value += ujson.Obj("path" -> next.toString, "target" -> target.toString)
          if (target.isAbsolute) resolved = target.getRoot
          pending = target.iterator().asScala.map(_.toString).toList ++ pending
        } else resolved = next
      }
    }
    (resolved, links)
  }
}

final class FileInput private(val path: Path, val record: ujson.Obj)
object FileInput {
  def capture(file: File, directory: File): FileInput = {
    directory.mkdirs()
    val (path, links) = InputCapture.resolve(file.toPath)
    val before = InputCapture.stamp(path)
    val bytes = Files.readAllBytes(path)
    require(before == InputCapture.stamp(path), s"input_not_captured:$file: changed during capture")
    val copy = Files.createTempFile(directory.toPath, "input-", ".input")
    Files.write(copy, bytes)
    require(copy.toFile.setReadOnly(), s"input_not_captured:$file: cannot seal copy")
    new FileInput(copy, ujson.Obj("source" -> file.toString, "resolved" -> path.toString,
      "copy" -> copy.toAbsolutePath.toString, "size" -> bytes.length,
      "sha256" -> InputCapture.hash(bytes), "symlinks" -> links))
  }
}

final class ElfInput private(val elf: ElfFile, val record: ujson.Obj)
object ElfInput {
  def capture(file: File, directory: File): ElfInput = {
    val input = FileInput.capture(file, directory)
    new ElfInput(new ElfFile(input.path.toFile), input.record)
  }
}

final class ToolInput private(val path: Path, val record: ujson.Obj, stamp: String, directory: File) {
  def verify(): Unit = {
    val before = InputCapture.stamp(path)
    val bytes = Files.readAllBytes(path)
    val after = InputCapture.stamp(path)
    require(before == stamp && after == stamp &&
      InputCapture.hash(bytes) == record("sha256").str,
      s"input_not_captured:tool:$path: changed before publication")
  }
  def run(args: String*): String = {
    verify()
    val output = Files.createTempFile(directory.toPath, "tool-", ".txt")
    var process: Process = null
    try {
      process = new ProcessBuilder((path.toString +: args).asJava)
        .redirectErrorStream(true).redirectOutput(output.toFile).start()
      require(process.waitFor(30, TimeUnit.SECONDS), s"input_not_captured:tool:$path: timeout")
      require(process.exitValue() == 0, s"input_not_captured:tool:$path: exit ${process.exitValue()}")
      verify()
      Files.readString(output)
    } finally {
      if (process != null) {
        // Stop descendants on failure, timeout, interruption, and successful leader exit.
        process.descendants().iterator().asScala.toSeq.reverse.foreach(_.destroyForcibly())
        if (process.isAlive) process.destroyForcibly()
        process.waitFor()
      }
      Files.deleteIfExists(output)
    }
  }
}
object ToolInput {
  def capture(name: String, directory: File): ToolInput = {
    directory.mkdirs()
    val candidates = if (name.contains(File.separator)) Seq(new File(name).toPath)
      else sys.env.getOrElse("PATH", "").split(File.pathSeparator, -1).toSeq.map(p => new File(p, name).toPath)
    val selected = candidates.find(p => Files.isRegularFile(p) && Files.isExecutable(p))
      .getOrElse(sys.error(s"input_not_captured:tool:$name: not executable"))
    val (path, links) = InputCapture.resolve(selected)
    val before = InputCapture.stamp(path)
    val bytes = Files.readAllBytes(path)
    require(before == InputCapture.stamp(path), s"input_not_captured:tool:$name: changed during capture")
    val copy = Files.createTempFile(directory.toPath, "tool-", ".bin")
    Files.write(copy, bytes); copy.toFile.setReadOnly()
    val record = ujson.Obj("source" -> name, "resolved" -> path.toString, "copy" -> copy.toString,
      "sha256" -> InputCapture.hash(bytes), "size" -> bytes.length, "symlinks" -> links)
    val tool = new ToolInput(path, record, before, directory)
    record("version") = tool.run("--version").trim
    tool
  }
}

object CapturedDisasm {
  def apply(elf: ElfFile, tool: ToolInput, directory: File): Map[BigInt, (Long, String)] = {
    val line = """^\s*([0-9a-f]+):\s+([0-9a-f]+)\s+(.+)$""".r
    elf.withSnapshotFile(directory) { snapshot =>
      tool.run("-d", snapshot.toString).linesIterator.collect {
        case line(addr, word, text) => BigInt(addr, 16) ->
          (java.lang.Long.parseLong(word, 16), text.replace('\t', ' ').trim)
      }.toMap
    }
  }
}
