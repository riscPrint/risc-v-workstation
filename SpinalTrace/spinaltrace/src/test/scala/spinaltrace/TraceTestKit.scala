package spinaltrace

import java.io.File

import org.scalatest.Assertions._

import scala.sys.process._

/** Helpers to run the SpinalTrace CLI on a simulation and query the resulting source-level DPDG. */
object TraceTestKit {
  val repo: File        = new File("..").getCanonicalFile
  val examplesDir: File = new File(repo, "examples/src/spinaltrace/examples")
  val cli: String       = sys.env.getOrElse("SPINALTRACE_CLI", new File(repo, "target/release/spinaltrace-cli").getPath)
  val simWorkspace      = "simWorkspace"

  def requireCli(): Unit =
    assume(new File(cli).canExecute, s"SpinalTrace CLI not found at $cli; run `cargo build --release -p spinaltrace-cli` in $repo")

  /** 1-based line of the first line of `file` containing `text`. */
  def lineOf(file: String, text: String, after: String = ""): Int = {
    val lines = scala.io.Source.fromFile(new File(examplesDir, file), "UTF-8").getLines().toVector
    val from  = if (after.isEmpty) 0 else lines.indexWhere(_.contains(after)).max(0)
    val i     = lines.indexWhere(_.contains(text), from)
    require(i >= 0, s"'$text' not found in $file")
    i + 1
  }

  case class Node(idx: Int, name: String, kind: String, file: String, line: Int, timestamp: Long,
                  simData: Option[String], modulePath: Seq[String]) {
    def fileName: String = new File(file).getName
    override def toString = s"#$idx $name @$fileName:$line t=$timestamp${simData.map(" = " + _).getOrElse("")}"
  }
  case class Edge(from: Node, to: Node, kind: String)

  case class Dpdg(nodes: Seq[Node], edges: Seq[Edge], summary: String) {
    def at(file: String, line: Int): Seq[Node] = nodes.filter(n => n.fileName == file && n.line == line)
    def lines(file: String): Set[Int]          = nodes.filter(_.fileName == file).map(_.line).toSet
    def named(name: String): Seq[Node]         = nodes.filter(_.name == name)
    def kinds: Set[String]                     = edges.map(_.kind).toSet
    def edgesFrom(n: Node): Seq[Edge]          = edges.filter(_.from == n)
    def has(from: Node => Boolean, to: Node => Boolean, kind: String): Boolean =
      edges.exists(e => e.kind == kind && from(e.from) && to(e.to))
    override def toString: String = summary
  }

  def onLine(file: String, line: Int): Node => Boolean = n => n.fileName == file && n.line == line
  def withName(name: String): Node => Boolean          = _.name == name

  def parse(json: ujson.Value, summary: String): Dpdg = {
    val nodes = json("vertices").arr.zipWithIndex.map { case (v, i) =>
      Node(i, v("name").str, v("kind").str, v("file").str, v("line").num.toInt, v("timestamp").num.toLong,
        v.obj.get("sim_data").flatMap(_.strOpt), v("module_path").arr.map(_.str).toSeq)
    }.toSeq
    val edges = json("edges").arr.map(e => Edge(nodes(e("from").num.toInt), nodes(e("to").num.toInt), e("kind").str)).toSeq
    Dpdg(nodes, edges, summary)
  }

  /** Run `spinaltrace-cli dyn-pdg` and parse its output. */
  def trace(pdg: File, vcd: File, criterion: String, extra: Seq[String] = Nil): Dpdg = {
    requireCli()
    val out = File.createTempFile("dynpdg", ".json")
    val log = new StringBuilder
    val cmd = Seq(cli, "dyn-pdg", "-s", criterion, "-p", pdg.getPath, "-v", vcd.getPath, "-o", out.getPath, "--summary") ++ extra
    val code = Process(cmd).!(ProcessLogger(l => log.append(l).append('\n'), l => log.append(l).append('\n')))
    assert(code == 0, s"CLI failed (${cmd.mkString(" ")}):\n$log")
    val d = parse(ujson.read(scala.io.Source.fromFile(out, "UTF-8").mkString), log.toString)
    out.delete()
    d
  }

  def waveOf(t: TracedSim[_], test: String): File = t.waveFile(test).getOrElse(fail(s"no VCD for test $test"))
}
