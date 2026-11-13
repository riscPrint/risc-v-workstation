package spinalwaves

import java.nio.charset.StandardCharsets
import java.nio.file.{Files, Path, Paths}
import scala.collection.mutable
import spinal.core._

/** Emits the HGLDD dialect consumed by the vendored tywaves-rs, after RTL generation. */
object HglddEmitter {
  def emit[T <: Component](report: SpinalReport[T], workspace: Path,
                          sourceRoots: Seq[Path] = SourceLocator.defaultRoots): Path = {
    val emitter = new Emitter[T](report, sourceRoots)
    val dir = workspace.resolve("spinalwaves/hgldd")
    Files.createDirectories(dir)
    val out = dir.resolve(report.toplevelName + ".dd")
    Files.write(out, ujson.write(emitter.document(), indent = 2).getBytes(StandardCharsets.UTF_8))
    out
  }

  private class Node(val name: String) {
    var data: Option[Data] = None
    var area: Option[Area] = None
    var leaf: Option[BaseType] = None
    val children = mutable.LinkedHashMap.empty[String, Node]
    def at(path: Seq[String]): Node = path.foldLeft(this)((n, field) => n.children.getOrElseUpdate(field, new Node(field)))
  }

  private class Emitter[T <: Component](report: SpinalReport[T], roots: Seq[Path]) {
    private val files = mutable.ArrayBuffer.empty[String]
    private val structs = mutable.ArrayBuffer.empty[ujson.Value]
    private val allocatedNames = mutable.HashSet.empty[String] ++ components(report.toplevel).map(_.definitionName)
    private val variableCache = mutable.AnyRefMap.empty[Component, Seq[ujson.Value]]
    private def structName(key: String): String = {
      val base = key + "_struct"
      var candidate = base
      var suffix = 1
      while (allocatedNames(candidate)) { candidate = base + "_" + suffix; suffix += 1 }
      allocatedNames += candidate
      candidate
    }
    private val enums = mutable.LinkedHashMap.empty[(SpinalEnum, SpinalEnumEncoding), Int]
    private def location(value: ScalaLocated): Option[ujson.Value] = SourceLocator(value, roots).map { loc =>
      // HGLDD paths are always absolute; SourceLocator itself retains the documented bare-name fallback.
      val path = Paths.get(loc.absPath).toAbsolutePath.normalize.toString
      // HGLDD file indexes are 1-based, as emitted by CIRCT (`hdl_file_index` uses the same convention).
      val idx = files.indexOf(path) match { case -1 => files += path; files.size; case i => i + 1 }
      ujson.Obj("file" -> idx, "begin_line" -> loc.line, "end_line" -> loc.line,
        "begin_column" -> loc.col, "end_column" -> loc.col)
    }
    private def withLocation(obj: ujson.Obj, value: ScalaLocated): ujson.Obj = {
      location(value).foreach(loc => obj("hgl_loc") = loc); obj
    }
    private def components(c: Component): Seq[Component] = Seq(c) ++ c.children.toSeq.flatMap(components)
    private def signals(c: Component): Seq[BaseType] = {
      val leaves = mutable.ArrayBuffer.empty[BaseType]
      c.dslBody.walkDeclarations {
        case bt: BaseType if bt.isNamed && bt.getName().nonEmpty && bt.getBitsWidth > 0 &&
          !report.prunedSignals.contains(bt) => leaves += bt
        case _ => ()
      }
      leaves.toSeq.sortBy(_.getName())
    }

    private def tree(c: Component): Node = {
      val root = new Node("")
      signals(c).foreach { bt =>
        val (name, fields) = HglNaming.localPath(bt)
        val full = Seq(name) ++ fields
        root.at(full).leaf = Some(bt)
        val (dataRoot, dataFields) = HglNaming.dataPath(bt)
        val prefix = full.dropRight(dataFields.length)
        var data: Data = dataRoot
        root.at(prefix).data = Some(data)
        dataFields.zipWithIndex.foreach { case (field, i) =>
          data = data.asInstanceOf[MultiData].elements.find(_._1 == field).get._2
          root.at(prefix ++ dataFields.take(i + 1)).data = Some(data)
        }
        dataRoot.getRefOwnersChain().collect { case a: Area if a.component == c && a.isNamed => a }
          .zipWithIndex.foreach { case (a, i) => root.at(full.take(i + 1)).area = Some(a) }
      }
      root
    }
    private def ordered(n: Node): Seq[Node] = {
      val children = n.children.values.toSeq
      // Vec elements in index order; a Vec node can also hold non-index names (BOOM: `f0_pc`), keep those after
      if (n.data.exists(_.isInstanceOf[Vec[_]])) children.sortBy(c => (scala.util.Try(c.name.toInt).getOrElse(Int.MaxValue), c.name))
      else children
    }
    private def expression(n: Node): ujson.Value = n.leaf match {
      case Some(bt) => ujson.Obj("sig_name" -> bt.getName())
      case None => ujson.Obj("opcode" -> "'{", "operands" -> ujson.Arr.from(ordered(n).map(expression)))
    }
    private def shape(n: Node): String = n.leaf match {
      case Some(bt: SpinalEnumCraft[_]) => s"enum:${System.identityHashCode(bt.spinalEnum)}:${bt.getEncoding.getName()}:${bt.getBitsWidth}"
      case Some(bt) => bt.getClass.getName + ":" + bt.getBitsWidth
      case None => ordered(n).map(c => c.name + ":" + shape(c)).mkString("{", ",", "}")
    }
    private def isDenseVec(n: Node): Boolean = n.data.exists(_.isInstanceOf[Vec[_]]) && {
      val vec = n.data.get.asInstanceOf[Vec[_]]
      ordered(n).map(_.name) == (0 until vec.length).map(_.toString) && n.children.nonEmpty &&
        ordered(n).map(shape).toSet.size == 1
    }

    private def variable(n: Node, key: String, withValue: Boolean): ujson.Obj = {
      val obj = ujson.Obj("var_name" -> n.name)
      n.data.foreach { d =>
        obj("source_lang_type_info") = TypeInfo.json(d, TypeInfo.decorated(d))
        withLocation(obj, d)
      }
      n.area.foreach { a =>
        obj("source_lang_type_info") = TypeInfo.json(a, TypeInfo.className(a))
        withLocation(obj, a)
      }
      if (withValue) obj("value") = expression(n)
      n.leaf match {
        case Some(bt) =>
          obj("type_name") = "logic"
          obj("packed_range") = ujson.Arr(bt.getBitsWidth - 1, 0)
          bt match {
            case e: SpinalEnumCraft[_] if e.spinalEnum.elements.forall(x => e.getEncoding.getValue(x).isValidLong) =>
              obj("enum_def_ref") = enums.getOrElseUpdate((e.spinalEnum, e.getEncoding), enums.size)
            case _ => ()
          }
        case None if isDenseVec(n) =>
          val prototype = variable(ordered(n).head, key + "_element", withValue = false)
          Seq("type_name", "packed_range", "unpacked_range", "enum_def_ref").foreach { k =>
            prototype.obj.get(k).foreach(v => obj(k) = v)
          }
          val childDims = obj.obj.get("unpacked_range").map(_.arr.toSeq).getOrElse(Seq.empty)
          obj("unpacked_range") = ujson.Arr.from(Seq(ujson.Num(n.children.size - 1), ujson.Num(0)) ++ childDims)
        case None =>
          val typeName = structName(key)
          obj("type_name") = typeName
          val fields = ordered(n).map(ch => variable(ch, key + "_" + ch.name, withValue = false))
          structs += ujson.Obj("kind" -> "struct", "obj_name" -> typeName, "port_vars" -> ujson.Arr.from(fields))
      }
      obj
    }

    private def variables(c: Component): Seq[ujson.Value] = variableCache.getOrElseUpdate(c, {
      tree(c).children.values.map(n => variable(n, c.definitionName + "_" + n.name, withValue = true)).toSeq
    })
    private def instance(child: Component): ujson.Value = withLocation(ujson.Obj(
      "name" -> child.getName(), "hdl_obj_name" -> child.getName(),
      "obj_name" -> child.definitionName, "module_name" -> child.definitionName,
      // Spinal can deduplicate different Scala shapes into the same RTL module. Existing
      // HGLDD instance overrides preserve each instance's fields and source metadata.
      "port_vars" -> ujson.Arr.from(variables(child)),
      "children" -> ujson.Arr.from(child.children.toSeq.sortBy(_.getName()).map(instance)),
      "source_lang_type_info" -> TypeInfo.json(child, TypeInfo.className(child))), child)

    def document(): ujson.Value = {
      // PhaseVerilog updates definitionName on deduplicated components to the emitted module name.
      val modules = components(report.toplevel).groupBy(_.definitionName).toSeq.sortBy(_._1).map { case (name, instances) =>
        val c = instances.head
        withLocation(ujson.Obj("kind" -> "module", "obj_name" -> name, "module_name" -> name,
          "port_vars" -> ujson.Arr.from(variables(c)),
          "children" -> ujson.Arr.from(c.children.toSeq.sortBy(_.getName()).map(instance)),
          "source_lang_type_info" -> TypeInfo.json(c, TypeInfo.className(c))), c)
      }
      val enumDefs = ujson.Obj.from(enums.toSeq.map { case ((enumDef, encoding), id) =>
        id.toString -> ujson.Obj.from(enumDef.elements.map(e => encoding.getValue(e).toString -> ujson.Str(TypeInfo.enumLabel(enumDef, e))))
      })
      modules.foreach(m => if (enums.nonEmpty) m("enum_defs") = enumDefs)
      ujson.Obj("HGLDD" -> ujson.Obj("version" -> "0.1.0", "file_info" -> ujson.Arr.from(files)),
        "objects" -> ujson.Arr.from(structs ++ modules))
    }
  }
}
