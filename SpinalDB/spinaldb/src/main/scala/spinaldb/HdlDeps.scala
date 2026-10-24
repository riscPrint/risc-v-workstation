package spinaldb

import java.io.File
import java.nio.file.{Files, Path}
import java.util.concurrent.TimeUnit

import scala.util.control.NonFatal

/** BlackBox dependency scan over private C8 copies, through the shared Python capture API.
  * Literal includes are captured recursively before Yosys. Unsupported contexts fail closed. */
object HdlDeps {
  case class Result(chunks: Seq[(String, Array[Byte])], problems: Seq[String], capture: String = "{}")

  case class Request(top: String, files: Seq[(String, File)], inline: Seq[(String, String)],
                     params: Seq[(String, Either[String, String])], timeoutS: Long = 120)

  private def request(r: Request): ujson.Value = ujson.Obj(
    "top" -> r.top,
    "files" -> ujson.Arr.from(r.files.map { case (l, f) => ujson.Arr(l, f.getAbsolutePath) }),
    "inline" -> ujson.Arr.from(r.inline.map { case (l, t) => ujson.Arr(l, t) }),
    "params" -> ujson.Arr.from(r.params.collect { case (n, Right(v)) => ujson.Arr(n, v) }),
    "timeout" -> ujson.Num(r.timeoutS.toDouble))

  private def result(r: ujson.Value): Result = Result(
    r("chunks").arr.toSeq.map(c => c(0).str -> java.util.Base64.getDecoder.decode(c(1).str)),
    r("problems").arr.toSeq.map(_.str), r.obj.get("capture").map(ujson.write(_)).getOrElse("{}"))

  def captureAll(requests: Seq[Request], files: Seq[File], sourceRoots: Seq[Path] = Nil,
                 optionalSourceRoots: Seq[Path] = Nil): (Seq[Result], Result) = {
    val valid = requests.filterNot(_.params.exists(_._2.isLeft))
    val batch = try {
      val response = call(ujson.Obj("operation" -> "many", "requests" -> ujson.Arr.from(valid.map(request)),
        "files" -> ujson.Arr.from(files.map(_.getAbsolutePath)),
        "source_roots" -> ujson.Arr.from(sourceRoots.map(_.toAbsolutePath.toString)),
        "optional_source_roots" -> ujson.Arr.from(optionalSourceRoots.map(_.toAbsolutePath.toString))))
      (response("results").arr.toSeq.map(result), result(response("files")))
    } catch { case NonFatal(e) =>
      val failed = Result(Nil, Seq(s"input_not_captured:hdl: $e"))
      (valid.map(_ => failed), failed)
    }
    val pending = batch._1.iterator
    (requests.map(r => if (r.params.exists(_._2.isLeft)) Result(Nil,
      r.params.collect { case (n, Left(why)) => s"generic $n: $why" }) else pending.next()), batch._2)
  }

  private def call(request: ujson.Value): ujson.Value = {
    val dir = Files.createTempDirectory("spinaldb-bbdeps-")
    try {
      val runner = processRunner.getOrElse(throw new IllegalStateException("process runner not found"))
      val input = dir.resolve("request.json"); val output = dir.resolve("result.json")
      Files.writeString(input, ujson.write(request))
      val p = new ProcessBuilder(sys.env.getOrElse("SPINALDB_PYTHON", "python3"), runner.getPath,
        "--scan", input.toString, output.toString)
        .redirectErrorStream(true).redirectOutput(dir.resolve("runner.log").toFile).start()
      def stop(): Unit = {
        p.destroy()
        if (!p.waitFor(10, TimeUnit.SECONDS)) p.destroyForcibly()
      }
      val hook = new Thread(() => stop(), "spinaldb-hdl-deps-cleanup")
      Runtime.getRuntime.addShutdownHook(hook)
      try p.waitFor() catch { case e: InterruptedException => stop(); throw e }
      finally try Runtime.getRuntime.removeShutdownHook(hook) catch { case _: IllegalStateException => }
      if (p.exitValue() != 0 || !Files.isRegularFile(output))
        throw new IllegalStateException("dependency runner failed: " + Files.readString(dir.resolve("runner.log")).takeRight(1000))
      ujson.read(Files.readString(output))
    } finally deleteTree(dir)
  }

  private def processRunner: Option[File] = {
    val bases = Seq(new File(System.getProperty("user.dir")),
      new File(getClass.getProtectionDomain.getCodeSource.getLocation.toURI))
    sys.env.get("SPINALDB_PROCESS_RUNNER").map(new File(_)).filter(_.isFile).orElse {
      bases.iterator.flatMap(f => Iterator.iterate(f)(_.getParentFile).takeWhile(_ != null))
        .map(new File(_, "SpinalDB/scripts/hdl-deps.py")).find(_.isFile)
    }
  }

  private def deleteTree(p: Path): Unit = try {
    val all = Files.walk(p)
    try all.sorted(java.util.Comparator.reverseOrder()).forEach(x => Files.deleteIfExists(x)) finally all.close()
  } catch { case NonFatal(_) => }
}
