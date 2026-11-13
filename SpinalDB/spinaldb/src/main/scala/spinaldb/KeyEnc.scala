package spinaldb

import spinal.core._
import spinal.core.internals._

/** The one encoder for values written into typed keys (`rvw.designdb/20`). Every encoded form is
  * self-delimiting and typed, so two different values never give the same text, and a sequence of
  * encoded values joined with any separator stays unambiguous:
  *
  *   - a string is a quoted literal (`str`): `"` and `\` escaped, and every control character
  *     (ExprText's register-token marks U+0001/U+0002 among them) and every surrogate written
  *     `\\uXXXX`, so a string can neither end early nor pose as a token, and SQLite's UTF-8 cannot
  *     merge two strings;
  *   - a name (class, field, signal path, generic) is kept as it is when it is a plain JVM name
  *     (`[A-Za-z0-9_$.]+`, not `null`), else quoted (`name`);
  *   - text that may hold register tokens, or a typed key, is length-framed (`framed`: `<n>:<text>`);
  *   - a number or boolean carries its type (`Int(1)`, `Long(1)`, `Boolean(true)`);
  *   - an enum-like Spinal value (assertion kind, severity, trigger, formal random kind, reset kind,
  *     clock edge, attribute kind, language) has a stable label (`label`), never its identity
  *     `toString` (`AssertStatementKind@1b2c3d`), which changes between runs. */
object KeyEnc {
  def str(s: String): String = {
    if (s == null) return "null"
    val sb = new StringBuilder(s.length + 2)
    sb += '"'
    s.foreach {
      case '"'  => sb ++= "\\\""
      case '\\' => sb ++= "\\\\"
      case c if c < 0x20 || (c >= 0x7f && c <= 0x9f) || Character.isSurrogate(c) || c == ' ' || c == ' ' =>
        sb ++= f"\\u${c.toInt}%04x"
      case c => sb += c
    }
    sb += '"'
    sb.toString
  }

  private val Plain = "[A-Za-z0-9_$.]+".r
  def name(s: String): String = if (s != null && s != "null" && Plain.pattern.matcher(s).matches()) s else str(s)

  /** `-` for null, else `<length>:<text>`: for text that is already a key or may hold register tokens. */
  def framed(s: String): String = if (s == null) "-" else s"${s.length}:$s"

  /** A primitive, string or big number with its type, or None for anything else (a subclass of a JDK
    * big-number class included). */
  def scalar(v: Any): Option[String] = v match {
    case null                    => Some("null")
    case s: String               => Some(str(s))
    case x: Int                  => Some(s"Int($x)")
    case x: Long                 => Some(s"Long($x)")
    case x: Short                => Some(s"Short($x)")
    case x: Byte                 => Some(s"Byte($x)")
    case x: Boolean              => Some(s"Boolean($x)")
    case x: Char                 => Some(s"Char(${str(x.toString)})")
    case x: Double               => Some(s"Double(${java.lang.Double.toString(x)})")
    case x: Float                => Some(s"Float(${java.lang.Float.toString(x)})")
    // `java.math.BigInteger` and `BigDecimal` are not final: a subclass (also inside a Scala `BigInt` or
    // `BigDecimal`) can override `toString`, so only the JDK classes themselves are read (round 14).
    case x: BigInt if LibraryClasses.exact(x.bigInteger.getClass, classOf[java.math.BigInteger])         => Some(s"BigInt(${x.bigInteger.toString})")
    case x: BigDecimal if LibraryClasses.exact(x.bigDecimal.getClass, classOf[java.math.BigDecimal])     => Some(s"BigDecimal(${x.bigDecimal.toString})")
    case x: java.math.BigInteger if LibraryClasses.exact(x.getClass, classOf[java.math.BigInteger])      => Some(s"BigInt(${x.toString})")
    case _                       => None
  }

  /** Hexadecimal payloads use the same exact-class allow-list as scalar values. Never call a
    * numeric method on a rejected subclass. Keep the incomplete marker outside any later hash. */
  def integerHex(v: BigInt): String =
    if (v == null) "null"
    else if (scalar(v).isDefined) v.bigInteger.toString(16)
    else s"$$incomplete:integer ${name(v.bigInteger.getClass.getName)}"

  /** A Scala `object` (singleton): its class name ends in `$` and has the static `MODULE$` field. */
  def isObject(v: AnyRef): Boolean =
    v.getClass.getName.endsWith("$") && v.getClass.getFields.exists(f => f.getName == "MODULE$" &&
      java.lang.reflect.Modifier.isStatic(f.getModifiers))

  /** Spinal's enum-like values that are plain instances (`val ASSERT = new AssertStatementKind`): by
    * their name in Spinal, matched by identity. */
  private val known: java.util.IdentityHashMap[AnyRef, String] = {
    val m = new java.util.IdentityHashMap[AnyRef, String]()
    m.put(AssertStatementKind.ASSERT, "ASSERT"); m.put(AssertStatementKind.ASSUME, "ASSUME"); m.put(AssertStatementKind.COVER, "COVER")
    m.put(AssertStatementTrigger.CLOCKED, "CLOCKED"); m.put(AssertStatementTrigger.INITIAL, "INITIAL")
    m.put(Operator.Formal.RANDOM_ANY_SEQ, "RANDOM_ANY_SEQ"); m.put(Operator.Formal.RANDOM_ANY_CONST, "RANDOM_ANY_CONST")
    m.put(Operator.Formal.RANDOM_ALL_SEQ, "RANDOM_ALL_SEQ"); m.put(Operator.Formal.RANDOM_ALL_CONST, "RANDOM_ALL_CONST")
    m
  }

  /** A stable label for an enum-like value: one of Spinal's named instances (`known`), a Scala
    * `object` by its class (`ERROR`, `ASYNC`, `RISING`, `COMMENT_ATTRIBUTE`; Spinal's own without the
    * `spinal.core.` prefix), a Java enum by class and constant. Anything else has no stable label:
    * `$incomplete:label <class>`. */
  def label(v: Any): String = v match {
    case null                              => "null"
    case r: AnyRef if known.containsKey(r) => known.get(r)
    case e: java.lang.Enum[_]              => name(e.getDeclaringClass.getName + "." + e.name)
    case o: AnyRef if isObject(o) && LibraryClasses.isSpinal(o.getClass) =>
      name(o.getClass.getName.stripSuffix("$").stripPrefix("spinal.core."))
    case o: AnyRef                         => s"$$incomplete:label ${o.getClass.getName}"
  }
}
