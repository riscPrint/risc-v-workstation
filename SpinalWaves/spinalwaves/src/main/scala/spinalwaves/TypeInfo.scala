package spinalwaves

import spinal.core._
import spinal.lib.{Flow, Stream}
import scala.util.control.NonFatal
import scala.reflect.runtime.{universe => ru}

private[spinalwaves] object TypeInfo {
  def className(value: AnyRef): String = {
    val name = value.getClass.getSimpleName.stripSuffix("$")
    if (name.isEmpty || name.contains("$anon")) {
      val parent = value.getClass.getSuperclass
      if (parent == null || parent == classOf[Object]) value match {
        case _: Area => "Area"
        case _: Bundle => "Bundle"
        case _: Component => "Component"
        case _ => "Object"
      } else parent.getSimpleName.stripSuffix("$")
    } else name
  }

  def name(data: Data): String = data match {
    case s: Stream[_] => s"Stream[${name(s.payload)}]"
    case f: Flow[_] => s"Flow[${name(f.payload)}]"
    case v: Vec[_] => s"Vec[${v.headOption.map(name).getOrElse("Data")}](${v.length})"
    case e: SpinalEnumCraft[_] => className(e.spinalEnum)
    case _: Bool => "Bool"
    case u: UInt => s"UInt(${u.getBitsWidth} bits)"
    case s: SInt => s"SInt(${s.getBitsWidth} bits)"
    case b: Bits => s"Bits(${b.getBitsWidth} bits)"
    case f: SFix => s"SFix(maxExp=${f.maxExp}, ${f.bitCount} bits)"
    case f: UFix => s"UFix(maxExp=${f.maxExp}, ${f.bitCount} bits)"
    case f: AFix => s"AFix(minRaw=${f.minRaw}, maxRaw=${f.maxRaw}, exp=${f.exp})"
    case other => className(other)
  }

  def decorated(data: Data): String = {
    val fixedOwner = data.getRefOwnersChain().reverse.collectFirst {
      case f: SFix => f: Data
      case f: UFix => f: Data
      case f: AFix => f: Data
    }
    val base = name(fixedOwner.getOrElse(data))
    val leaves = data.flatten
    val prefix = if (leaves.nonEmpty && leaves.forall(_.isInput)) "in "
      else if (leaves.nonEmpty && leaves.forall(_.isOutput)) "out "
      else if (leaves.nonEmpty && leaves.forall(_.isInOut)) "inout "
      else if (leaves.nonEmpty && leaves.forall(_.isReg)) "Reg " else ""
    prefix + base
  }

  /** Best effort: reflect primary-constructor names and read matching fields, never evaluate user methods. */
  def params(value: AnyRef): Seq[ujson.Value] = try {
    val mirror = ru.runtimeMirror(value.getClass.getClassLoader)
    val cls = mirror.classSymbol(value.getClass)
    val ctor = cls.primaryConstructor
    if (ctor == ru.NoSymbol) Seq.empty
    else ctor.asMethod.paramLists.flatten.map { symbol =>
      val p = ujson.Obj("name" -> symbol.name.decodedName.toString, "type" -> symbol.typeSignature.toString)
      val field = Iterator.iterate[Class[_]](value.getClass)(_.getSuperclass).takeWhile(_ != null)
        .flatMap(_.getDeclaredFields).find(_.getName == symbol.name.decodedName.toString)
      field.foreach { f =>
        f.setAccessible(true)
        val v = f.get(value)
        v match {
          case null => p("value") = "null"
          case _: java.lang.Number | _: java.lang.Boolean | _: String | _: java.lang.Character => p("value") = v.toString
          case _ => ()
        }
      }
      p
    }
  } catch { case NonFatal(_) => Seq.empty }

  /** Source val names survive backend enum-name allocation, which can append suffixes per encoding. */
  def enumLabel(enumDef: SpinalEnum, element: SpinalEnumElement[_]): String = try {
    Iterator.iterate[Class[_]](enumDef.getClass)(_.getSuperclass).takeWhile(_ != null)
      .flatMap(_.getDeclaredFields).filter(f => classOf[SpinalEnumElement[_]].isAssignableFrom(f.getType))
      .find { f => f.setAccessible(true); f.get(enumDef).asInstanceOf[AnyRef] eq element }
      .map(f => scala.reflect.NameTransformer.decode(f.getName)).getOrElse(element.getName())
  } catch { case NonFatal(_) => element.getName() }

  def json(value: AnyRef, typeName: String): ujson.Obj = {
    val info = ujson.Obj("type_name" -> typeName)
    val parameters = params(value)
    if (parameters.nonEmpty) info("params") = ujson.Arr.from(parameters)
    info
  }
}
