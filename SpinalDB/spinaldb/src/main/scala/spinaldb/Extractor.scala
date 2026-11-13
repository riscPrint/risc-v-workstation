package spinaldb

import java.io.{ByteArrayOutputStream, File}
import java.nio.file.{Files, Path}
import java.util.zip.GZIPOutputStream

import spinal.core._
import spinal.core.internals._
import spinaltrace.{ExtractOptions, Locations, Netlist, PdgExtractor, PdgModel}
import spinalwaves.{HglNaming, HglddEmitter}

import scala.collection.mutable
import scala.collection.mutable.ArrayBuffer
import scala.util.control.NonFatal

/** One `clock_domains` row: control signal paths, kinds and polarities, and the typed key of each control. */
case class CdRow(clock: String, reset: String, resetKind: String, resetHigh: String, enable: String, soft: String, edge: String,
                 enableHigh: String, softHigh: String, clockKey: String, resetKey: String, enableKey: String, softKey: String)

/** What to put into the database besides the netlist tables. */
case class DbOptions(
    sourceRoots: Seq[Path] = DbOptions.DefaultSourceRoots,
    /** SpinalTrace's statement-level PDG (`pdg_*` tables and the `pdg.json` artifact). Needs the
      * SpinalTrace naming phase, so `SpinalDB.elaborate` adds it when this is on. */
    pdg: Boolean = true,
    /** Also store the PDG's vertices and edges as tables (`pdg_vertices`, `pdg_edges`). Off by default:
      * they are large (about 55 MB for BOOM small) and duplicate the `pdg.json` artifact. */
    pdgTables: Boolean = false,
    /** SpinalBlocks diagram JSON as the `blocks.json` artifact. */
    blocks: Boolean = true,
    /** SpinalWaves HGLDD as the `hgldd/<top>.dd` artifact. */
    hgldd: Boolean = true,
    /** Extra `meta` rows (core name, config, source revision, ...). */
    meta: Seq[(String, String)] = Nil,
    /** External sources of BlackBoxes, by definition name: hashed into the BlackBox's body
      * fingerprint (with any `addRTLPath` files and inline HDL). A BlackBox with no body to hash is
      * written `$incomplete:`, so `rvw query diff` cannot call a design with it identical. */
    blackboxSources: Map[String, Seq[Path]] = Map.empty,
    log: String => Unit = s => println(s"[SpinalDB] $s")
)

object DbOptions {
  /** Only this default value has optional search roots. Caller-supplied roots are required,
    * including a fresh sequence with the same paths as these defaults. */
  private[spinaldb] val DefaultSourceRoots: Seq[Path] = spinalwaves.SourceLocator.defaultRoots
}

/** Walks an elaborated design and writes the `rvw.designdb/20` tables (see SpinalDB/README.md). */
class Extractor(report: SpinalReport[_ <: Component], opts: DbOptions) {
  private val top    = report.toplevel
  private val locs   = new Locations(opts.sourceRoots.map(_.toFile))
  private val pruned = identitySet[BaseType](report.prunedSignals)
  private val warnings = mutable.LinkedHashMap[String, Int]()
  private def warn(msg: String): Unit = warnings(msg) = warnings.getOrElse(msg, 0) + 1

  private def identitySet[T <: AnyRef](xs: Iterable[T]): java.util.Set[T] = {
    val s = java.util.Collections.newSetFromMap(new java.util.IdentityHashMap[T, java.lang.Boolean]())
    xs.foreach(s.add)
    s
  }

  // ------------------------------------------------------------------ naming
  private def instPath(c: Component): Seq[String] = HglNaming.instancePath(c)
  private def rtlPath(bt: BaseType): String = HglNaming.rtlPath(bt)
  private def memPath(m: Mem[_]): String = (instPath(m.component) :+ m.getName()).mkString(".")

  /** `bt` as seen from `from`: relative to it when inside it, else the full path. */
  private def rel(bt: BaseType, from: Component): String = {
    val p = instPath(bt.component)
    val f = instPath(from)
    if (p.startsWith(f)) (p.drop(f.length) :+ bt.getName()).mkString(".") else rtlPath(bt)
  }

  private def generated(bt: BaseType): Boolean = Netlist.isGenerated(bt)
  /** `when_File_l12` / `switch_File_l40`: Spinal names a condition or switch value after its source
    * line, so the name changes when an unrelated line is added. Such a signal is generated only when
    * Spinal gave it that name (`SpinalDB.elaborate` tags it, see `GeneratedNamePhase`): keys then
    * treat it as a temporary (by content, never by name) and `rvw query diff` hides it the same way.
    * A signal the user named like that (a register `when_Test_l12`) is compared by its name. */
  private val LocName = "^(when|switch)_\\w+_l\\d+(_\\d+)?$".r
  // A generated signal's tags are part of its template or key (raw: a clock domain in a tag is written
  // with raw control keys, as in a register's template).
  private val text = new ExprText(rel, generated, domainOf = bt => cdRaw(bt.clockDomain), cdRawOf = cdRaw,
    tagsOf = bt => signalTags(bt, raw = true))
  private def render(e: Expression, from: Component): String = if (e == null) null else text.render(e, from)
  private def key(e: Expression, from: Component): String = if (e == null) "-" else text.key(e, from)

  private def className(v: AnyRef): String = {
    val n = v.getClass.getSimpleName.stripSuffix("$")
    if (n.isEmpty || n.contains("$anon")) {
      val p: Class[_] = v.getClass.getSuperclass
      if (p == null || p == classOf[Object]) "anonymous" else p.getSimpleName.stripSuffix("$")
    } else n
  }

  private def typeName(bt: BaseType): String = if (!LibraryClasses.signal(bt.getClass))
    s"$$incomplete:signal ${bt.getClass.getName}" else bt match {
    // The enum's complete definition under its encoding is part of the type (`binarySequential` and
    // `graySequential` have the same width; a reordered or custom-encoded enum has other values).
    // A long definition is hashed (`State@seq{h:...}`); an incomplete one keeps `$incomplete:`.
    case e: SpinalEnumCraft[_] =>
      val k = text.enumKey(e.spinalEnum, e.getEncoding)
      if (k.length <= 160 || ExprText.isIncomplete(k)) k
      else k.substring(0, k.indexOf('{') max 0) + "{h:" + sha256(Seq(k.getBytes("UTF-8"))).take(32) + "}"
    case _: Bool               => "Bool"
    case _: UInt               => "UInt"
    case _: SInt               => "SInt"
    case _: Bits               => "Bits"
    case other                 => className(other)
  }

  private def width(bt: BaseType): Int = try bt.getBitsWidth catch { case NonFatal(_) => 0 }

  /** Type of the bundle/Vec directly owning `bt` (`Stream`, `MicroOp`, `Vec(4)`), when there is one. */
  private def dataType(bt: BaseType): String = bt.parent match {
    case null      => null
    case v: Vec[_] => s"Vec(${v.length})"
    case other     => className(other)
  }

  private def rootOf(bt: BaseType): Data = { var d: Data = bt; var g = 0; while (d.parent != null && g < 64) { d = d.parent; g += 1 }; d }

  /** Typed Spinal path (SpinalWaves' `hglPath`). Compiler temporaries, and fields of an unnamed bundle or
    * Vec (e.g. declared in a `for` loop; `hglPath` would call its root `io`), keep their RTL path. */
  private def hasSpinalPath(bt: BaseType): Boolean = {
    val root = rootOf(bt)
    !generated(bt) && !root.isUnnamed && root.getName() != null && root.getName().nonEmpty
  }
  private def spinalPath(bt: BaseType): String =
    if (!hasSpinalPath(bt)) rtlPath(bt)
    else {
      val (root, fields) = HglNaming.hglPath(bt)
      if (fields.isEmpty) root else root + "." + fields
    }

  // ------------------------------------------------------------------ ids
  private val compId  = new java.util.IdentityHashMap[Component, Integer]()
  private val sigId   = new java.util.IdentityHashMap[BaseType, Integer]()
  private val memSig  = new java.util.IdentityHashMap[Mem[_], Integer]()
  private val memId   = new java.util.IdentityHashMap[Mem[_], Integer]()
  private val areaId  = new java.util.IdentityHashMap[Area, Integer]()
  private val cdIds   = mutable.LinkedHashMap[CdRow, Int]()
  private val cdOf    = new java.util.IdentityHashMap[ClockDomain, Integer]()
  private val files   = mutable.LinkedHashMap[String, Int]()

  private def fileId(path: String): Integer =
    if (path == null || path.isEmpty) null else Int.box(files.getOrElseUpdate(path, files.size + 1))

  /** Source-location hint only, never a modelling decision. SpinalDB's entry points create the
    * toplevel's clock domain; those frames do not identify the user's hardware source. */
  private def ownFrame(s: ScalaLocated): Boolean =
    try locs.frame(s.getScalaTrace()).exists(_.getClassName.startsWith("spinaldb.")) catch { case NonFatal(_) => false }

  private def loc(s: ScalaLocated): (Integer, Integer) = {
    val l = try { if (ownFrame(s)) PdgModel.Location.unknown else locs.of(s) } catch { case NonFatal(_) => PdgModel.Location.unknown }
    if (l.file.isEmpty) (null, null) else (fileId(l.file), Int.box(l.line))
  }
  /** A user component's own class body (its constructor frame), not a shared base class such as BOOM's
    * `BoomModule` in types.scala. spinal.lib components keep the user line that instantiates them. */
  private def componentLoc(c: Component): (Integer, Integer) = {
    val own = try {
      val t = c.getScalaTrace()
      if (t == null) None
      else ScalaLocated.filterStackTrace(t.getStackTrace).find(f => f.getClassName == c.getClass.getName && !f.getClassName.startsWith("spinal.") && f.getLineNumber > 0)
    } catch { case NonFatal(_) => None }
    own match {
      case Some(fr) =>
        val (file, line, _) = spinaltrace.SourceInfo.locate(fr, opts.sourceRoots.map(_.toFile))
        (fileId(file), Int.box(line))
      case None => loc(c)
    }
  }

  private val LineComment = """@ (\S+) l(\d+)""".r
  private def locA(a: AssignmentStatement): (Integer, Integer) = {
    // Statements Spinal adds after the component body (FSM encoding, clock wiring) only have SpinalDB's
    // entry point as user frame: use Spinal's line comment instead, when it has one.
    val l = try {
      if (!ownFrame(a)) locs.ofAssignment(a)
      else a.locationString match {
        case LineComment(f, n) if !f.startsWith("SpinalDB") => PdgModel.Location(f, n.toInt, 0)
        case _                                              => PdgModel.Location.unknown
      }
    } catch { case NonFatal(_) => PdgModel.Location.unknown }
    if (l.file.isEmpty) (null, null) else (fileId(l.file), Int.box(l.line))
  }

  // ------------------------------------------------------------------ clock domains
  private val cdRole = new java.util.IdentityHashMap[BaseType, String]()

  private def cdSignalPath(b: BaseType): String =
    if (b == null) null
    else if (b.component != null) rtlPath(b)
    else top.pulledDataCache.get(b).collect { case p: BaseType => rtlPath(p) }.getOrElse(b.getName())

  /** Everything a register or memory port depends on in its clock domain: clock and edge, reset signal,
    * kind and polarity, clock enable and its polarity, soft reset and its polarity (row of `clock_domains`),
    * and the typed key of each control signal (`ExprText.key` from the toplevel), so a generated
    * clock enable (`clockEnable = io.a > 1`) is compared by its logic, not by its unstable name. */
  private def cdRow(cd: ClockDomain, raw: Boolean): CdRow = {
    val c = cd.config
    CdRow(cdSignalPath(cd.clock), cdSignalPath(cd.reset), if (cd.reset != null || cd.softReset != null) KeyEnc.label(c.resetKind) else null,
      if (cd.reset != null) (c.resetActiveLevel == HIGH).toString else null, cdSignalPath(cd.clockEnable),
      cdSignalPath(cd.softReset), KeyEnc.label(c.clockEdge),
      if (cd.clockEnable != null) (c.clockEnableActiveLevel == HIGH).toString else null,
      if (cd.softReset != null) (c.softResetActiveLevel == HIGH).toString else null,
      controlKey(cd.clock, raw), controlKey(cd.reset, raw), controlKey(cd.clockEnable, raw), controlKey(cd.softReset, raw))
  }

  private def cdKey(cd: ClockDomain): CdRow = {
    val row = cdRow(cd, raw = false)
    if (LibraryClasses.exact(cd.getClass, classOf[ClockDomain]) &&
      LibraryClasses.exact(cd.config.getClass, classOf[ClockDomainConfig])) row
    else row.copy(clockKey = "$incomplete:clock domain identity " + row.clockKey)
  }

  /** The clock domain inside a generated register's template: the same row with raw control keys, whose
    * generated registers stay tokens (edges of the register graph), so no id is needed while ids are made. */
  private val cdRawMemo = new java.util.IdentityHashMap[ClockDomain, String]()
  private val cdRawBusy = new java.util.IdentityHashMap[ClockDomain, java.lang.Boolean]()
  private def cdRaw(cd: ClockDomain): String =
    if (cd == null) "-"
    // A domain met again while its own row is written (a control signal whose tag names the domain):
    // cut, so incomplete.
    else if (!LibraryClasses.exact(cd.getClass, classOf[ClockDomain]) ||
      !LibraryClasses.exact(cd.config.getClass, classOf[ClockDomainConfig])) "$incomplete:clock domain identity"
    else if (cdRawBusy.containsKey(cd)) "$incomplete:clock domain cycle"
    else {
      var v = cdRawMemo.get(cd)
      if (v == null) {
        cdRawBusy.put(cd, true)
        // Each field is length-framed: control keys hold commas and register tokens.
        v = cdRow(cd, raw = true).productIterator.map(v => KeyEnc.framed(v.asInstanceOf[String])).mkString(",")
        cdRawBusy.remove(cd)
        cdRawMemo.put(cd, v)
      }
      v
    }

  /** Typed key of a clock-domain control signal, from the toplevel: a named signal by its path (its own
    * assignments are compared where it is driven), a compiler temporary by its logic. A signal outside
    * the netlist that no component pulled in is not hardware: `unpulled:<name>`. */
  private def controlKey(b: BaseType, raw: Boolean): String =
    if (b == null) null
    else {
      val s: BaseType = if (b.component != null) b else top.pulledDataCache.get(b).collect { case p: BaseType => p }.orNull
      if (s == null) s"unpulled:${KeyEnc.name(b.getName())}" else if (raw) text.rawKey(s, top) else text.key(s, top)
    }

  private def clockDomainId(cd: ClockDomain): Integer = {
    if (cd == null) return null
    val cached = cdOf.get(cd)
    if (cached != null) return cached
    val id = cdIds.getOrElseUpdate(cdKey(cd), cdIds.size + 1)
    cdOf.put(cd, id)
    id
  }

  private def collectClockSignals(all: Seq[Component]): Unit = {
    val cds = mutable.LinkedHashSet[ClockDomain]()
    for (c <- all) {
      if (c.clockDomain != null) cds += c.clockDomain
      c.dslBody.walkStatements {
        case bt: BaseType if bt.isReg && bt.clockDomain != null => cds += bt.clockDomain
        case st: Statement => st.foreachClockDomain(cd => if (cd != null) cds += cd)
      }
    }
    def mark(b: BaseType, role: String): Unit = if (b != null) {
      if (!cdRole.containsKey(b)) cdRole.put(b, role)
      for (c <- all; p <- c.pulledDataCache.get(b)) p match {
        case pb: BaseType if !cdRole.containsKey(pb) => cdRole.put(pb, role)
        case _                                       =>
      }
    }
    cds.foreach { cd =>
      mark(cd.clock, "clock"); mark(cd.reset, "reset"); mark(cd.softReset, "soft_reset"); mark(cd.clockEnable, "clock_enable")
    }
  }

  // ------------------------------------------------------------------ extraction
  /** Tags and attributes of a signal, memory or memory port as stable text (null when none), in the
    * order Spinal holds them (`SpinalTagReady.spinalTags`, a `LinkedHashSet` in insertion order). The
    * order is part of the key: the Verilog and VHDL emitters write attributes in that order (with two
    * `init` attributes the netlist takes the last one), and `getTag`/`findTag` return the first tag of
    * a class. Every value is written with `KeyEnc` (typed, strings escaped). A tag whose payload cannot
    * be read as content, or an attribute with behavior the key does not evaluate, is `$incomplete:`. */
  private def tagsText(tags: Iterable[SpinalTag], raw: Boolean = false, owner: BaseType = null): String = {
    val parts = tags.toSeq.map {
      case a: Attribute => attrText(a)
      case t if Extractor.IgnoredTags(t.getClass) => null
      // In a generated signal's own key: the role tag `ClockDomain` puts on its control signal names
      // the domain this signal controls. That domain is compared where registers and ports use it;
      // expanding it here would expand this signal again.
      // These short forms are for Spinal's own classes only: a subclass can override the accessors they
      // read and add fields they do not show (round 14), so it is read by its fields below.
      case t: ClockDomainBoolTag if raw && owner != null && Extractor.RoleTags(t.getClass) && (Extractor.roleSignal(t) eq owner) =>
        s"tag ${t.getClass.getName}:self"
      // A toplevel input pulled from outside the netlist (a clock domain's pin): keyed by the driver's name.
      case t: ExternalDriverTag if LibraryClasses.exact(t.getClass, classOf[ExternalDriverTag]) =>
        s"tag spinal.core.ExternalDriverTag:${Option(t.driver).map(d => KeyEnc.str(d.getName())).getOrElse("null")}"
      // How a memory word splits into symbols: each symbol's name and bit range (`width` and `mask`
      // of a mapping are derived from its range). The list must be a Scala library collection of
      // Spinal's own `MemSymbolesMapping`s; else not modelled.
      case t: MemSymbolesTag if LibraryClasses.exact(t.getClass, classOf[MemSymbolesTag]) =>
        val ms = t.mapping
        val parts = if (ms == null || !scalaStd(ms)) None else {
          val ps = ms.toSeq.map {
            case m: MemSymbolesMapping if LibraryClasses.exact(m.getClass, classOf[MemSymbolesMapping]) => tagValue(m.range, 1, raw).map(r => s"${KeyEnc.str(m.name)}:$r")
            case _ => None
          }
          if (ps.forall(_.isDefined)) Some(ps.flatten) else None
        }
        parts.map(_.mkString("tag spinal.core.MemSymbolesTag:[", ",", "]")).getOrElse(s"$$incomplete:tag ${t.getClass.getName}")
      // Anything else by its content (`tagValue`): a Scala `object` by its class and fields, a case class
      // field by field. A tag whose payload cannot be read as content (its `toString` may print a name only, as
      // `ClockDomainReportTag(clk)` does for a whole clock domain) is not modelled.
      case t => tagValue(t, 0, raw) match {
        case Some(v) => s"tag ${KeyEnc.name(t.getClass.getName)}:$v"
        case None    => s"$$incomplete:tag ${t.getClass.getName}"
      }
    }.filter(_ != null)
    if (parts.isEmpty) null else parts.mkString("; ")
  }

  /** An attribute as the emitters see it (`VerilogBase.emitSyntaxAttributes`, the VHDL emitter):
    * its family (string, integer or flag: the emitters match on `AttributeString`, `AttributeInteger`,
    * `AttributeFlag`), name, value, kind (`attributeKind`: syntax or comment), the languages it is
    * emitted in (`isLanguageReady`), and the `SpinalTag` flags that steer elaboration. A subclass
    * (`Verilator.public`, a user class) adds its class and every field it declares; it is
    * `$incomplete:` when it overrides a method of its base class the key does not evaluate, or holds a
    * field that is not content. A file-naming attribute adds the file's hash (`attrFile`). */
  private def attrText(a: Attribute): String = try {
    val (base, family, value) = a match {
      case s: AttributeString  => (classOf[AttributeString], "string", "=" + KeyEnc.str(s.value))
      case i: AttributeInteger => (classOf[AttributeInteger], "integer", s"=Int(${i.value})")
      case _: AttributeFlag    => (classOf[AttributeFlag], "flag", "")
      case _                   => return s"$$incomplete:attribute ${a.getClass.getName}"
    }
    val langs = Seq(Language.VERILOG -> "verilog", Language.SYSTEM_VERILOG -> "systemverilog", Language.VHDL -> "vhdl")
      .collect { case (l, n) if a.isLanguageReady(l) => n }
    val flags = Seq("moveToSyncNode" -> a.moveToSyncNode, "duplicative" -> a.duplicative, "driverShouldNotChange" -> a.driverShouldNotChange,
      "canSymplifyHost" -> a.canSymplifyHost, "allowMultipleInstance" -> a.allowMultipleInstance, "ioTag" -> a.ioTag)
      .collect { case (n, true) => n }
    val sub = if (LibraryClasses.exact(a.getClass, base)) "" else " " + attrSubclass(a, base)
    s"attr $family(${KeyEnc.str(a.getName)}$value) kind=${KeyEnc.label(a.attributeKind())} lang=[${langs.mkString(",")}] " +
      s"flags=[${flags.mkString(",")}]$sub" + (a match { case s: AttributeString => attrFile(s); case _ => "" })
  } catch { case NonFatal(e) => s"$$incomplete:attribute ${a.getClass.getName} (${e.getClass.getName})" }

  /** What a subclass of an attribute base class adds: its class, and every field declared below the
    * base (a Scala `object`'s static fields included) by content. A method of the base class it
    * overrides must be one `attrText` evaluates (or `toString`, `equals`, `hashCode`, `sameType`, which
    * only steer error messages and duplicate removal before the tags are read); any other override
    * (`isAssignedTo`, `apply`) may change elaboration in a way the key does not show: incomplete. */
  private def attrSubclass(a: Attribute, base: Class[_]): String = {
    val evaluated = Set("getName", "attributeKind", "isLanguageReady", "moveToSyncNode", "duplicative", "driverShouldNotChange",
      "canSymplifyHost", "allowMultipleInstance", "ioTag", "toString", "equals", "hashCode", "sameType")
    val baseMethods = base.getMethods.map(m => (m.getName, m.getParameterTypes.toSeq)).toSet
    val overrides = mutable.LinkedHashSet[String]()
    val fields = ArrayBuffer[java.lang.reflect.Field]()
    if (KeyEnc.isObject(a)) a.getClass.getDeclaredFields.filter(f => java.lang.reflect.Modifier.isStatic(f.getModifiers)).foreach(fields += _)
    var k: Class[_] = a.getClass
    while (k != null && k != base) {
      k.getDeclaredMethods.filter(m => !m.isSynthetic && !m.isBridge && !java.lang.reflect.Modifier.isStatic(m.getModifiers) &&
        baseMethods((m.getName, m.getParameterTypes.toSeq)) && !evaluated(m.getName)).foreach(m => overrides += m.getName)
      k.getDeclaredFields.filterNot(f => java.lang.reflect.Modifier.isStatic(f.getModifiers)).foreach(fields += _)
      k = k.getSuperclass
    }
    val cls = s"class ${KeyEnc.name(a.getClass.getName)}"
    if (overrides.nonEmpty) s"$$incomplete:attribute $cls overrides ${overrides.toSeq.sorted.mkString(",")}"
    else {
      val values = for (vs <- fieldValues(a, keyedFields(fields.toSeq), 0, raw = false);
                        cs <- constantValues(a.getClass, 0, raw = false)) yield vs ++ cs
      values match {
        case Some(vs) => s"$cls fields{${vs.mkString(",")}}"
        case None     => s"$$incomplete:attribute $cls has a field or constant that is not content"
      }
    }
  }

  /** `name=value` of each field (sorted by name, then declaring class), or None when one cannot be
    * read or is not content (`tagValue`). */
  private def fieldValues(o: AnyRef, fs: Seq[java.lang.reflect.Field], depth: Int, raw: Boolean): Option[Seq[String]] = {
    val vs = fs.sortBy(f => (f.getName, f.getDeclaringClass.getName)).map { f =>
      val owner = if (java.lang.reflect.Modifier.isStatic(f.getModifiers)) null else o
      (try { f.setAccessible(true); Some(f.get(owner)) } catch { case NonFatal(_) => None })
        .flatMap(v => tagValue(v, depth + 1, raw)).map(v => s"${KeyEnc.name(f.getName)}=$v")
    }
    if (vs.forall(_.isDefined)) Some(vs.flatten) else None
  }

  /** Leave out fields with the Scala compiler's exact bookkeeping shape. */
  private def keyedFields(fs: Seq[java.lang.reflect.Field]): Seq[java.lang.reflect.Field] =
    fs.filter(f => Extractor.fieldRole(f) == Extractor.FieldRole.Payload)

  /** `name=value` of each constant `final val` of a class and what it inherits (no field holds them;
    * read from the Scala signature, `Extractor.scalaSig`), sorted by name. None when the signature
    * cannot be read or a value is not content. */
  private def constantValues(c: Class[_], depth: Int, raw: Boolean): Option[Seq[String]] =
    Extractor.scalaSig(c).flatMap { sig =>
      val vs = sig.constants.map { case (n, v) => tagValue(v, depth + 1, raw).map(x => s"${KeyEnc.name(n)}=$x") }
      if (vs.forall(_.isDefined)) Some(vs.flatten) else None
    }

  private def signalTags(bt: BaseType, raw: Boolean = false): String = {
    val tags = tagsText(bt.getTags(), raw, bt)
    val scope = bt.rootScopeStatement
    val local = scope != null && scope.parentStatement != null
    if (local) Option(tags).filter(_.nonEmpty).map(_ + ";").getOrElse("") + "spinaldb:conditionalDeclaration"
    else tags
  }

  private def componentTags(c: Component): String = {
    val parts = Seq("instance" -> tagsText(c.getTags()), "definition" -> tagsText(c.definition.getTags()))
      .collect { case (k, t) if t != null => s"$k: $t" }
    if (parts.isEmpty) null else parts.mkString("; ")
  }

  /** Static object fields and inherited instance fields, excluding compiler bookkeeping. */
  private def payloadFields(c: Class[_]): Option[Seq[java.lang.reflect.Field]] = {
    val out = Seq.newBuilder[java.lang.reflect.Field]
    c.getDeclaredFields.filter(f => java.lang.reflect.Modifier.isStatic(f.getModifiers)).foreach(out += _)
    var k: Class[_] = c
    while (k != null && k != classOf[Object]) {
      k.getDeclaredFields.filterNot(f => java.lang.reflect.Modifier.isStatic(f.getModifiers)).foreach(out += _)
      k = k.getSuperclass
    }
    Some(keyedFields(out.result()))
  }

  /** A Scala `object` by its payload: its class, every field it holds (`payloadFields`) and every
    * constant `final val` (`constantValues`) by content, fields read by reflection. An object with
    * neither is its class. A field that cannot be read or whose
    * value is not content (`tagValue`), makes it None (not modelled). */
  private def objectValue(o: AnyRef, depth: Int, raw: Boolean): Option[String] = {
    val fields = try payloadFields(o.getClass) catch { case NonFatal(_) => None }
    val cls = KeyEnc.name(o.getClass.getName)
    for (fs <- fields; vs <- fieldValues(o, fs, depth, raw); cs <- constantValues(o.getClass, depth, raw))
      yield if (vs.isEmpty && cs.isEmpty) cls else (vs ++ cs).mkString(s"$cls{", ",", "}")
  }

  /** The keyed instance fields, read without calling methods of the payload class. */
  private def instanceFields(c: Class[_]): Option[Seq[java.lang.reflect.Field]] = {
    val out = Seq.newBuilder[java.lang.reflect.Field]
    var k: Class[_] = c
    while (k != null && k != classOf[Object]) {
      k.getDeclaredFields.filterNot(f => java.lang.reflect.Modifier.isStatic(f.getModifiers)).foreach(out += _)
      k = k.getSuperclass
    }
    Some(keyedFields(out.result()))
  }

  /** Only exact classes from the loaded Scala library may supply collection iteration methods. */
  private def scalaStd(x: AnyRef): Boolean = LibraryClasses.isScala(x.getClass)

  /** A tag payload as content (`KeyEnc` forms), or None when part of it cannot be read as content:
    * primitives, strings and big numbers typed (`KeyEnc.scalar`); Scala objects by class and every
    * field they hold (`objectValue`); a signal by its RTL path and a memory by its path (both compared
    * by their own rows); a clock domain by its whole `clock_domains` row (control paths, kinds,
    * polarities and typed keys, each length-framed); standard Scala collections element by element
    * (`seq[...]`; a set or map in sorted order, `set{...}`, `map{k->v,...}`, so the order of a hash
    * does not matter); an array as `array[...]`; and any other `Product` (a case class) by its class,
    * every field it holds (its own and inherited, `instanceFields`, as `name=value` sorted by name) and
    * every constant `final val`, all read by reflection. No method a user class can override decides the
    * key (round 14: `productIterator`, `productElement`, `productElementNames` were overridden to hide
    * fields): a "standard" collection must be a class of the Scala library itself (its jar, not only a
    * `scala.` name), and a clock domain a `ClockDomain` itself (a subclass is a `Product`, read by its
    * fields). Other collection classes are not modelled (a field beside the elements could hold more).
    * `raw`: a clock domain by its raw row (`cdRaw`), for tags inside a generated register's template. */
  private def tagValue(v: Any, depth: Int, raw: Boolean = false): Option[String] = {
    def all(xs: Iterable[Any]): Option[Seq[String]] = {
      val r = xs.toSeq.map(tagValue(_, depth + 1, raw))
      if (r.forall(_.isDefined)) Some(r.flatten) else None
    }
    def std(x: AnyRef) = scalaStd(x)
    v match {
      case _ if depth > 8                          => None
      case x if KeyEnc.scalar(x).isDefined         => KeyEnc.scalar(x)
      case r: Range if std(r)                      => Some(s"Range(${r.start},${r.end},${r.step},${r.isInclusive})")
      case m: scala.collection.Map[_, _] if std(m) =>
        val es = m.toSeq.map { case (k, x) => for (ks <- tagValue(k, depth + 1, raw); xs <- tagValue(x, depth + 1, raw)) yield s"$ks->$xs" }
        if (es.forall(_.isDefined)) Some(es.flatten.sorted.mkString("map{", ",", "}")) else None
      case s: scala.collection.Set[_] if std(s)    => all(s).map(_.sorted.mkString("set{", ",", "}"))
      case s: scala.collection.Seq[_] if std(s)    => all(s).map(_.mkString("seq[", ",", "]"))
      case a: Array[_]                             => all(a.toSeq).map(_.mkString("array[", ",", "]"))
      case o: AnyRef if KeyEnc.isObject(o)         => objectValue(o, depth, raw)
      case cd: ClockDomain if LibraryClasses.exact(cd.getClass, classOf[ClockDomain]) && raw => Some(s"cd(${cdRaw(cd)})")
      case cd: ClockDomain if LibraryClasses.exact(cd.getClass, classOf[ClockDomain]) =>
        Some(cdKey(cd).productIterator.map(x => KeyEnc.framed(x.asInstanceOf[String])).mkString("cd(", ",", ")"))
      case bt: BaseType if LibraryClasses.signal(bt.getClass) => Some("signal " + KeyEnc.name(rtlPath(bt)))
      case m: Mem[_] if LibraryClasses.exact(m.getClass, classOf[Mem[_]]) => Some("mem " + KeyEnc.name(memPath(m)))
      case p: Product if !p.isInstanceOf[Data] && !p.isInstanceOf[Iterable[_]] =>
        val fields = try instanceFields(p.getClass) catch { case NonFatal(_) => None }
        for (fs <- fields; vs <- fieldValues(p.asInstanceOf[AnyRef], fs, depth, raw); cs <- constantValues(p.getClass, depth, raw))
          yield vs.mkString(s"${KeyEnc.name(p.getClass.getName)}(", ",", ")") + (if (cs.isEmpty) "" else cs.mkString("{", ",", "}"))
      case _                                       => None
    }
  }

  /** An attribute naming a file (its name says `file` or `path`, or its value is a readable file): the
    * synthesis tool reads that file, so its contents are part of the key; unreadable: not modelled. */
  private def attrFile(a: AttributeString): String = {
    val path = new File(String.valueOf(a.value)).getAbsolutePath
    attributeFiles.get(path) match {
      case Some(Some(bytes)) => s" contents ${sha256(Seq(bytes))}"
      case Some(None) => s" $$incomplete:attribute input_not_captured:${KeyEnc.str(a.value)}"
      case None if a.getName.toLowerCase.matches(".*(file|path).*") =>
        s" $$incomplete:attribute input_not_captured:${KeyEnc.str(a.value)}"
      case _ => ""
    }
  }

  private var attributeFiles = Map.empty[String, Option[Array[Byte]]]
  private var inputCapture = "{}"
  private val blackboxInputs = new java.util.IdentityHashMap[BlackBox, HdlDeps.Request]()
  private val blackboxScans = new java.util.IdentityHashMap[BlackBox, HdlDeps.Result]()

  /** Discover all external consumers first. One shared Capture owns every file, including files
    * shared by several BlackBoxes or attributes. No solver starts until this set is copied. */
  private def captureInputs(components: Seq[Component]): Unit = {
    val attributes = mutable.LinkedHashSet[String]()
    def tags(owner: SpinalTagReady): Unit = owner.getTags().foreach {
      case a: AttributeString =>
        val f = new File(String.valueOf(a.value))
        if (f.isFile || a.getName.toLowerCase.matches(".*(file|path).*")) attributes += f.getAbsolutePath
      case _ =>
    }
    components.foreach { c =>
      tags(c); tags(c.definition)
      c.dslBody.walkStatements { case st: SpinalTagReady => tags(st); case _ => }
      c match {
        case bb: BlackBox if bb.isBlackBox =>
          val r = HdlDeps.Request(bb.definitionName,
            bb.listRTLPath.toSeq.map(p => s"rtl $p" -> new File(p)) ++
              opts.blackboxSources.getOrElse(bb.definitionName, Nil).map(p => s"user $p" -> p.toFile),
            InlineCapture.text(bb).getOrElse(Nil), bb.genericElements.toSeq.map { case (n, v) => (n, genericVerilog(v)) })
          blackboxInputs.put(bb, r)
        case _ =>
      }
    }
    val navigation = mutable.LinkedHashSet[File]()
    (report.generatedSourcesPaths ++ report.rtlSourcesPaths).foreach(p => navigation += new File(p).getAbsoluteFile)
    val boxes = components.collect { case bb: BlackBox if bb.isBlackBox => bb }
    val requests = boxes.map(blackboxInputs.get).distinct
    val defaults = opts.sourceRoots eq DbOptions.DefaultSourceRoots
    val batch = HdlDeps.captureAll(requests, attributes.toSeq.map(new File(_)) ++ navigation,
      if (defaults) Nil else opts.sourceRoots, if (defaults) opts.sourceRoots else Nil)
    val scans = requests.zip(batch._1).toMap
    boxes.foreach(bb => blackboxScans.put(bb, scans(blackboxInputs.get(bb))))
    val bytes = batch._2.chunks.toMap
    attributeFiles = attributes.map(p => p -> bytes.get(p)).toMap
    inputCapture = batch._2.capture
    batch._2.problems.foreach(warn)
  }

  private def sha256(chunks: Seq[Array[Byte]]): String = {
    val md = java.security.MessageDigest.getInstance("SHA-256")
    chunks.foreach { c => md.update(s"${c.length}:".getBytes("UTF-8")); md.update(c) }
    md.digest().map(b => f"${b & 0xff}%02x").mkString
  }

  /** A BlackBox generic as typed text; a value of a kind not listed here is not modelled. */
  private def genericText(v: Any, bb: BlackBox): String = v match {
    case bt: BaseType if !LibraryClasses.signal(bt.getClass) => s"$$incomplete:generic ${bt.getClass.getName}"
    case bt: BaseType =>
      bt.getTags().collectFirst { case t: GenericValue if LibraryClasses.exact(t.getClass, classOf[GenericValue]) => t.e } match {
        case Some(e) => s"${bt.getClass.getSimpleName}[${width(bt)}] ${KeyEnc.framed(text.key(e, if (bb.parent != null) bb.parent else bb))}"
        case None    => s"$$incomplete:generic ${bt.getClass.getName}"
      }
    case v @ SpinalApi.VerilogValue(x) if LibraryClasses.exact(v.getClass, classOf[SpinalApi.VerilogValue]) => s"verilog ${KeyEnc.str(x)}"
    case x: String        => s"String ${KeyEnc.str(x)}"
    case x: Int           => s"Int $x"
    case x: Double        => s"Double $x"
    case x: Boolean       => s"Boolean $x"
    case x: TimeNumber if LibraryClasses.exact(x.getClass, classOf[TimeNumber]) =>
      KeyEnc.scalar(x.toBigDecimal).map("Time " + _).getOrElse("$incomplete:generic TimeNumber")
    case null             => "null"
    case other            => s"$$incomplete:generic ${other.getClass.getName}"
  }

  /** A BlackBox generic as the Verilog value Yosys takes in `chparam -set` (`HdlDeps`), or why it
    * cannot be passed (the dependency set under it is then unknown). */
  private def genericVerilog(v: Any): Either[String, String] = v match {
    case bt: BaseType if !LibraryClasses.signal(bt.getClass) => Left("unsupported signal generic class")
    case x: Int                                    => Right(x.toString)
    case x: Long                                   => Right(x.toString)
    case x: BigInt if KeyEnc.scalar(x).isDefined    => Right(x.bigInteger.toString)
    case x: Boolean                                => Right(if (x) "1'b1" else "1'b0")
    case x: String if !x.exists(c => c == '"' || c == '\\' || c.isControl || c == ';' || c == '#') => Right("\"" + x + "\"")
    case v @ SpinalApi.VerilogValue(x) if LibraryClasses.exact(v.getClass, classOf[SpinalApi.VerilogValue]) && x.nonEmpty && !x.exists(c => c.isWhitespace || c == ';' || c == '#' || c == '"') => Right(x)
    case bt: BaseType => bt.getTags().collectFirst { case t: GenericValue if LibraryClasses.exact(t.getClass, classOf[GenericValue]) => t.e } match {
      case Some(b: BoolLiteral) if ExprText.modelled(b.getClass) => Right(if (b.value) "1'b1" else "1'b0")
      case Some(l: BitVectorLiteral) if ExprText.plainLiteral(l).exists(_.signum >= 0) =>
        Right(s"${l.bitCount}'h${KeyEnc.integerHex(l.value)}")
      case other => Left(s"a ${bt.getClass.getSimpleName} generic of ${other.map(_.getClass.getSimpleName).getOrElse("no value")} cannot be passed to Yosys")
    }
    case null  => Left("no value")
    case other => Left(s"a ${other.getClass.getSimpleName} value cannot be passed to Yosys")
  }


  /** One `blackboxes` row: generics, libraries, the RTL paths and inline HDL of the external body,
    * and the body fingerprint over its complete HDL dependency set (`HdlDeps`: inline HDL,
    * `addRTLPath` files, user `blackboxSources`, every file they `include`, the generics passed and
    * the compilation context). No body, or anything the scan cannot determine (an unreadable file,
    * an include, an undefined module, a VHDL body or library, no Yosys): `$incomplete:blackbox body`. */
  private def blackboxRow(bb: BlackBox): (String, String, String, String, String) = {
    val generics = bb.genericElements.map { case (n, v) => s"${KeyEnc.name(n)}=${genericText(v, bb)}" }.mkString("; ")
    val capturedInline = InlineCapture.text(bb)
    val inline = capturedInline.getOrElse(Nil)
    val inputs = blackboxInputs.get(bb)
    val files = inputs.files
    val libraries = bb.librariesUsages.toSeq.sorted
    val scan =
      if (capturedInline.isLeft) HdlDeps.Result(Nil, Seq(capturedInline.left.getOrElse("input_not_captured:inline")))
      else if (inline.isEmpty && files.isEmpty) HdlDeps.Result(Nil, Seq("no inline HDL, RTL path or supplied source"))
      else if (libraries.nonEmpty) HdlDeps.Result(Nil, Seq(s"VHDL libraries ${libraries.mkString(", ")} are outside the body"))
      else blackboxScans.get(bb)
    val body = if (scan.problems.nonEmpty || scan.chunks.isEmpty) null else sha256(scan.chunks.map(_._2))
    val from = if (body != null) scan.chunks.map(_._1).mkString("; ")
               else (inline.map(i => s"inline ${i._1}") ++ files.map(_._1)).mkString("; ")
    val key = s"definition=${KeyEnc.name(bb.definitionName)}; generics=[$generics]; libraries=[${libraries.map(KeyEnc.str).mkString(",")}]; " +
      s"simWhitebox=${bb.isSpinalSimWb}; body=" + (if (body != null) body else
        s"$$incomplete:blackbox body (${scan.problems.mkString("; ")})")
    if (body == null) warn(s"BlackBox ${bb.definitionName}: body incomplete (${scan.problems.mkString("; ")})")
    (generics, bb.listRTLPath.toSeq.mkString("; "), body, from, key)
  }

  private case class ReadState(id: Int, port: MemPortStatement, mem: Mem[_], comp: Component, cd: ClockDomain, width: Int)

  /** Statement ids, conditions and memory-read state from one ordered netlist walk. */
  private final class StatementWalker(db: DbWriter, startSignalId: Int) {
    private var nextSig = startSignalId
    val resetValue = new java.util.IdentityHashMap[BaseType, String]()
    val edges      = new java.util.HashSet[java.lang.Long]()
    val kindCode   = Map("data" -> 0, "cond" -> 1, "sel" -> 2, "init" -> 3, "blackbox" -> 4)
    val kindName   = kindCode.map(_.swap)
    def edge(src: Int, dst: Int, kind: String): Unit =
      edges.add((src.toLong << 32) | (dst.toLong << 3) | kindCode(kind))

    private val tAssign = db.table("assignments", "id", "target_id", "component_id", "kind", "range", "source", "enable", "mask", "key", "cond_id", "seq", "file_id", "line")
    private val tReads  = db.table("assign_reads", "assignment_id", "signal_id", "kind")
    private val tConds  = db.table("conds", "id", "parent_id", "component_id", "kind", "expr", "keys", "key", "signal_id", "file_id", "line")
    private val tCondR  = db.table("cond_reads", "cond_id", "signal_id")
    private val tPorts  = db.table("mem_ports", "id", "memory_id", "component_id", "kind", "address", "data", "enable", "write_enable", "mask", "clock_domain_id", "cond_id", "key", "file_id", "line", "output_id")
    private val tStmts  = db.table("statements", "id", "component_id", "kind", "key", "clock_domain_id", "cond_id", "file_id", "line")
    var nStmt = 0
    var nAssign, nCond, nPort = 0

    def idOf(bt: BaseType): Option[Int] = {
      val i = sigId.get(bt)
      if (i == null) { warn(s"signal outside the netlist read: ${bt.getName()}"); None } else Some(i)
    }
    def memIdOf(m: Mem[_]): Option[Int] = Option(memSig.get(m)).map(_.intValue)

    // Only a net attachment is bidirectional. An AnalogDriver's data and enable remain readers,
    // and a digital read of an analog net does not drive the net back. Spinal can slice either end
    // of an attachment when it joins pads of different widths.
    def analogNet(e: Expression): Option[BaseType] = e match {
      case bt: BaseType if bt.isAnalog || bt.isInOut => Some(bt)
      case a: BitVectorBitAccessFixed => analogNet(a.source)
      case a: BitVectorRangedAccessFixed => analogNet(a.source)
      case _ => None
    }

    // A synchronous port owns state distinct from the memory array. Keep it even when Spinal
    // assigns the port expression straight to a named output (there need not be a reg BaseType).
    val readStates = ArrayBuffer[ReadState]()
    val readStateIds = new java.util.IdentityHashMap[MemPortStatement, Integer]()
    def readState(port: MemPortStatement): Int = {
      val previous = readStateIds.get(port)
      if (previous != null) return previous.intValue
      val (m, cd, w, operands) = port match {
        case r: MemReadSync => (r.mem, r.clockDomain, r.width, Seq((r.address: Expression, "sel"), (r.readEnable: Expression, "sel")))
        case r: MemReadWrite => (r.mem, r.clockDomain, r.width, Seq((r.address: Expression, "sel"),
          (r.chipSelect: Expression, "sel"), (r.writeEnable: Expression, "cond"), (r.data: Expression, "data"), (r.mask: Expression, "cond")))
      }
      nextSig += 1
      val id = nextSig
      readStateIds.put(port, id)
      readStates += ReadState(id, port, m, m.component, cd, w)
      memIdOf(m).foreach(edge(_, id, "data"))
      // Conservative for write-through modes too: data/mask may affect the registered output.
      operands.foreach { case (expr, kind) => reads(expr, kind, (src, k) => edge(src, id, k)) }
      id
    }

    /** Leaves an expression reads: (signal id, kind) with kind data or sel (mux selects, dynamic
      * indexes, memory addresses and enables). */
    def reads(e: Expression, kind: String, out: (Int, String) => Unit): Unit = e match {
      case null            =>
      case bt: BaseType    => idOf(bt).foreach(out(_, kind))
      case _: Literal      =>
      case m: BinaryMultiplexer => reads(m.cond, "sel", out); reads(m.whenTrue, kind, out); reads(m.whenFalse, kind, out)
      case m: Multiplexer  => reads(m.select, "sel", out); m.inputs.foreach(reads(_, kind, out))
      case a: BitVectorBitAccessFloating    => reads(a.source, kind, out); reads(a.bitId, "sel", out)
      case a: BitVectorRangedAccessFloating => reads(a.source, kind, out); reads(a.offset, "sel", out)
      case r: MemReadAsync      => memIdOf(r.mem).foreach(out(_, kind)); reads(r.address, "sel", out)
      case r: MemReadSync       => out(readState(r), kind)
      case r: MemReadWrite      => out(readState(r), kind)
      case r: SpinalApi.AsyncWritePort => memIdOf(r.mem).foreach(out(_, kind)); reads(r.address, "sel", out)
      case other           => other.foreachExpression(reads(_, kind, out))
    }

    /** Condition context: innermost cond id and the signals read by every enclosing condition. */
    case class Ctx(comp: Component, cond: Integer, condReads: List[Int])

    /** A condition row. `typedKeys` is what selects the branch after the condition's own key (a
      * `switch` branch's case keys, `ExprText.switchBranchKey`), `keyExprs` the keys it reads. */
    def newCond(ctx: Ctx, kind: String, expr: Expression, exprText: String, keys: String, keyExprs: Seq[Expression],
                at: ScalaLocated, flags: String = "", typedKeys: String = ""): Ctx = {
      nCond += 1
      val (f, l) = if (at == null) (null, null) else loc(at)
      val sig: Integer = expr match { case bt: BaseType => sigId.get(bt); case _ => null }
      val typed = key(expr, ctx.comp) + typedKeys + flags
      tConds.add(nCond, ctx.cond, compId.get(ctx.comp), kind, exprText, keys, typed, sig, f, l)
      val rs = mutable.LinkedHashSet[Int]()
      reads(expr, "cond", (i, _) => rs += i)
      keyExprs.foreach(reads(_, "cond", (i, _) => rs += i))
      rs.foreach(i => tCondR.add(nCond, i))
      ctx.copy(cond = nCond, condReads = rs.toList ++ ctx.condReads)
    }

    def addAssign(target: Int, ctx: Ctx, kind: String, range: String, source: Expression, sourceText: String,
                  enable: String, extraReads: Seq[(Expression, String)], fl: (Integer, Integer),
                  typedKey: String, mask: String = null): Unit = {
      nAssign += 1
      tAssign.add(nAssign, target, compId.get(ctx.comp), kind, range, sourceText, enable, mask, typedKey, ctx.cond, nAssign,
        fl._1, fl._2)
      val rs = mutable.LinkedHashSet[(Int, String)]()
      val k  = if (kind == "init") "init" else "data"
      reads(source, k, (i, kk) => rs += ((i, kk)))
      extraReads.foreach { case (e, kk) => reads(e, kk, (i, _) => rs += ((i, kk))) }
      rs.foreach { case (i, kk) => tReads.add(nAssign, i, kk); edge(i, target, kk) }
      if (kind != "init") ctx.condReads.foreach(i => edge(i, target, "cond"))
    }

    def caseKey(k: Expression, c: Component): String = k match {
      case kb: SwitchStatementKeyBool if kb.key != null =>
        ExprText.maskedText(kb.key).getOrElse("$incomplete:masked literal")
      case kb: SwitchStatementKeyBool => render(kb.cond, c)
      case other => render(other, c)
    }

    /** A memory port row. `key` holds every behavior setting of the port (`ExprText.MemPortFields`:
      * width, read-under-write and during-write policies, vital flag; operands as typed keys; its tags);
      * the clock domain is compared through `clock_domain_id`, the enclosing condition through `cond_id`.
      * A port class or field this does not model makes the key `$incomplete:`. */
    def memPort(m: Mem[_], ctx: Ctx, kind: String, port: MemPortStatement, address: Expression, data: Expression,
                enable: Expression, wen: Expression, mask: Expression, cd: ClockDomain, at: ScalaLocated): Unit = {
      nPort += 1
      val (f, l) = loc(at)
      val c = ctx.comp
      val (rw, dw, width) = port match {
        case r: MemReadAsync      => (ExprText.rw(r.readUnderWrite), "", r.width)
        case r: MemReadSync       => (ExprText.rw(r.readUnderWrite), "", r.width)
        case r: MemReadWrite      => (ExprText.rw(r.readUnderWrite), ExprText.dw(r.duringWrite), r.width)
        case r: SpinalApi.AsyncWritePort => (ExprText.rw(r.readUnderWrite), ExprText.dw(r.duringWrite), r.width)
        case w: MemWrite          => ("", "", w.width)
        case _                    => ("", "", -1)
      }
      val handled = ExprText.MemPortFields(port.getClass)
      val known = handled.nonEmpty && ExprText.modelled(port.getClass)
      val key = (if (known) "" else s"$$incomplete:port ${port.getClass.getName} ") +
        s"$kind<width=$width,$rw,$dw,vital=${port.isVital}> address ${key0(address, c)} data ${key0(data, c)} " +
        s"enable ${key0(enable, c)} write_enable ${key0(wen, c)} mask ${key0(mask, c)}" +
        Option(tagsText(port match { case t: SpinalTagReady => t.getTags(); case _ => Nil })).map(" tags " + _).getOrElse("")
      val output: Integer = port match {
        case _: MemReadSync | _: MemReadWrite => Int.box(readState(port))
        case _ => null
      }
      if (output != null) ctx.condReads.foreach(i => edge(i, output, "cond"))
      tPorts.add(nPort, memId.getOrDefault(m, null), compId.get(c), kind, render(address, c), render(data, c),
        render(enable, c), render(wen, c), render(mask, c), clockDomainId(cd), ctx.cond, key, f, l, output)
    }
    def key0(e: Expression, c: Component): String = if (e == null) "-" else key(e, c)

    /** A statement that is not an assignment, a condition or a memory port (`statements` table). */
    def otherStatement(ctx: Ctx, st: Statement, kind: String, key: String, cd: ClockDomain, at: ScalaLocated): Unit = {
      nStmt += 1
      val (f, l) = if (at == null) (null, null) else loc(at)
      tStmts.add(nStmt, compId.get(ctx.comp), kind, key, clockDomainId(cd), ctx.cond, f, l)
    }

    // The byte/word mask of a masked write is a write enable per lane: a `cond` dependency like the enable.
    def memWrite(m: Mem[_], ctx: Ctx, address: Expression, data: Expression, enables: Seq[Expression], mask: Expression,
                 at: ScalaLocated): Unit =
      memIdOf(m).foreach { target =>
        val c  = ctx.comp
        val en = enables.filter(e => e != null && !(e.isInstanceOf[Literal] && ExprText.modelled(e.getClass) && e.asInstanceOf[Literal].getValue() == 1))
        val typed = s"mem_write[${key(address, c)}] := ${key(data, c)} en ${en.map(key(_, c)).mkString("&")} mask ${key(mask, c)}"
        addAssign(target, ctx, "mem_write", s"(${render(address, c)})", data, render(data, c),
          if (en.isEmpty) null else en.map(render(_, c)).mkString(" && "),
          Seq((address, "sel")) ++ en.map(e => (e, "cond")) ++ Option(mask).map(e => (e, "cond")), loc(at), typed,
          render(mask, c))
      }

    def walkScope(scope: ScopeStatement, ctx: Ctx): Unit = {
      if (!LibraryClasses.exact(scope.getClass, classOf[ScopeStatement]))
        otherStatement(ctx, null, "scope", s"$$incomplete:scope ${scope.getClass.getName}", null, null)
      scope.foreachStatements {
        case w: WhenStatement =>
          val e = render(w.cond, ctx.comp)
          walkScope(w.whenTrue, newCond(ctx, "when", w.cond, e, null, Nil, w, ExprText.whenIdentity(w)))
          if (w.whenFalse.nonEmpty) walkScope(w.whenFalse, newCond(ctx, "else", w.cond, e, null, Nil, w, ExprText.whenIdentity(w)))
        case sw: SwitchStatement =>
          val v = render(sw.value, ctx.comp)
          // A case is selected by its keys and (when keys can overlap) by no earlier key matching; the
          // default by no key matching: every case's keys, empty cases included (ExprText.switchBranchKey).
          val keyOf: Expression => String = key(_, ctx.comp)
          sw.elements.foreach { el =>
            walkScope(el.scopeStatement, newCond(ctx, "case", sw.value, v, el.keys.map(caseKey(_, ctx.comp)).mkString(", "),
              ExprText.switchBranchReads(sw, el), el, ExprText.switchFlags(sw), ExprText.switchBranchKey(sw, el, keyOf)))
          }
          if (sw.defaultScope != null && sw.defaultScope.nonEmpty)
            walkScope(sw.defaultScope, newCond(ctx, "default", sw.value, v, null, ExprText.switchBranchReads(sw, null), sw,
              ExprText.switchFlags(sw), ExprText.switchBranchKey(sw, null, keyOf)))
        case a: AssignmentStatement =>
          val bt = a.finalTarget
          if (pruned.contains(bt)) () else idOf(bt).foreach { target =>
            // `init` is the reset value, `initial` the power-on value: different hardware, different kinds.
            val stmtKind = ExprText.assignmentKind(a)
            val isInit = stmtKind == "init"
            val c = ctx.comp
            val (range, idx, rangeKey) = a.target match {
              case t: BitAssignmentFixed       => (s"(${t.bitId})", Nil, s"(${t.bitId})")
              case t: RangedAssignmentFixed    => (s"(${t.hi} downto ${t.lo})", Nil, s"(${t.hi} downto ${t.lo})")
              case t: BitAssignmentFloating    => (s"(${render(t.bitId, c)})", Seq((t.bitId: Expression, "sel")), s"(${key(t.bitId, c)})")
              case t: RangedAssignmentFloating => (s"(${render(t.offset, c)}, ${t.bitCount} bits)", Seq((t.offset: Expression, "sel")),
                s"(${key(t.offset, c)}, ${t.bitCount})")
              case _: BaseType                 => (null, Nil, "")
              case t                           => (null, Nil, s"($$incomplete:target ${t.getClass.getName})")
            }
            val src = render(a.source, c)
            if (isInit) {
              val prev = resetValue.get(bt)
              resetValue.put(bt, if (prev == null || range != null) Option(prev).map(_ + "; ").getOrElse("") + Option(range).getOrElse("") + src else src)
            }
            addAssign(target, ctx, if (isInit) "init" else if (stmtKind == "initial") "initial" else "data", range, a.source, src,
              null, idx, locA(a), (if (stmtKind.startsWith("$incomplete:")) stmtKind else "") + ExprText.targetIdentity(a.target) + s"$rangeKey := ${key(a.source, c)}")
            if (!isInit && (bt.isAnalog || bt.isInOut))
              analogNet(a.source).flatMap(idOf).foreach(edge(target, _, "data"))
          }
        case bt: BaseType if !LibraryClasses.signal(bt.getClass) =>
          // Do not lose an unsupported generated declaration merely because nothing named reads it.
          otherStatement(ctx, bt, "declaration", s"$$incomplete:signal ${bt.getClass.getName}", null, bt)
        case _: BaseType | _: Mem[_] =>
        case w: MemWrite =>
          memPort(w.mem, ctx, "write", w, w.address, w.data, null, w.writeEnable, w.mask, w.clockDomain, w)
          memWrite(w.mem, ctx, w.address, w.data, Seq(w.writeEnable), w.mask, w)
        case rw: MemReadWrite =>
          memPort(rw.mem, ctx, "read_write", rw, rw.address, rw.data, rw.chipSelect, rw.writeEnable, rw.mask, rw.clockDomain, rw)
          memWrite(rw.mem, ctx, rw.address, rw.data, Seq(rw.chipSelect, rw.writeEnable), rw.mask, rw)
        case r: MemReadSync =>
          memPort(r.mem, ctx, "read_sync", r, r.address, null, r.readEnable, null, null, r.clockDomain, r)
        case r: MemReadAsync =>
          memPort(r.mem, ctx, "read_async", r, r.address, null, null, null, null, null, r)
        case r: SpinalApi.AsyncWritePort =>
          // Its clock domain is the write's: compared like the other write ports.
          memPort(r.mem, ctx, "read_async_write", r, r.address, r.data, null, r.writeEnable, r.mask, r.clockDomain, r)
          memWrite(r.mem, ctx, r.address, r.data, Seq(r.writeEnable), r.mask, r)
        case a: AssertStatement =>
          // Assertions, assumptions and covers: kind, condition, message, severity, trigger, clock domain.
          // Kind, severity and trigger by stable labels (their `toString` is an identity hash); each
          // message part typed: a string escaped, a signal or expression by its length-framed key.
          val handled = Set("cond", "message", "severity", "kind", "trigger", "loc", "clockDomain")
          val msg = a.message.map {
            case x: String     => KeyEnc.str(x)
            case e: Expression => "expr " + KeyEnc.framed(key(e, ctx.comp))
            case x             => s"$$incomplete:message ${x.getClass.getName}"
          }.mkString(",")
          val k = (if (ExprText.params(a.getClass).subsetOf(handled) && LibraryClasses.exact(a.getClass, classOf[AssertStatement])) "" else
            s"$$incomplete:statement ${a.getClass.getName} ") +
            s"${KeyEnc.label(a.kind)} ${key(a.cond, ctx.comp)} severity ${KeyEnc.label(a.severity)} trigger ${KeyEnc.label(a.trigger)} " +
            s"message [$msg]" +
            Option(tagsText(a.getTags())).map(" tags " + _).getOrElse("")
          otherStatement(ctx, a, "assert", k, a.clockDomain, a)
        case other =>
          // Allow-list: a statement kind this extractor does not model makes its component undetermined.
          warn(s"statement not modelled: ${other.getClass.getName}")
          otherStatement(ctx, other, "other", s"$$incomplete:statement ${other.getClass.getName}", null,
            other match { case sl: ScalaLocated => sl; case _ => null })
      }
    }

    def write(components: Seq[Component]): Unit = {
      components.foreach { c =>
        walkScope(c.dslBody, Ctx(c, null, Nil))
        c match {
          case bb: BlackBox if bb.isBlackBox =>
            val ios = bb.getAllIo.toSeq
            for (o <- ios if o.isOutput || o.isInOut; i <- ios if (i.isInput || i.isInOut) && (i ne o))
              edge(sigId.get(i), sigId.get(o), "blackbox")
          case _ =>
        }
      }
      opts.log(s"$nAssign assignments, $nCond conditions, ${edges.size} dependency edges")

    }
  }

  private def writeSignalsAndMemories(db: DbWriter, components: Seq[Component], sigList: Seq[BaseType], memList: Seq[Mem[_]],
      resetValue: java.util.IdentityHashMap[BaseType, String], readStates: Seq[ReadState]): Unit = {
    // ---- areas, signals, memories
    val tArea = db.table("areas", "id", "component_id", "parent_id", "name", "path", "class_name", "file_id", "line")
    def areaOf(owners: Seq[Any], c: Component): Integer = {
      val chain = owners.collect { case a: Area if a.component == c && a.isNamed => a }
      var parent: Integer = null
      var prevName: String = null
      var path = ""
      chain.foreach { a =>
        val full = a.getName()
        val name = if (prevName != null && full.startsWith(prevName + "_")) full.substring(prevName.length + 1) else full
        path = if (path.isEmpty) name else path + "." + name
        val existing = areaId.get(a)
        parent = if (existing != null) existing else {
          val id = areaId.size + 1
          areaId.put(a, id)
          val (f, l) = loc(a)
          tArea.add(id, compId.get(c), parent, name, path, className(a), f, l)
          Int.box(id)
        }
        prevName = full
      }
      parent
    }

    val tSig = db.table("signals", "id", "component_id", "area_id", "name", "path", "spinal_path", "kind", "direction", "type",
      "width", "data_type", "clock_domain_id", "reset_value", "clock_role", "generated", "pruned", "tags", "port_index", "file_id",
      "line")
    // Each component's ports in the order its Verilog module declares them (Spinal's emitter:
    // `getOrdredNodeIo` without suffix fields such as a Stream's `fire`).
    val portIndex = new java.util.IdentityHashMap[BaseType, Integer]()
    components.foreach { c =>
      c.getOrdredNodeIo.filterNot(io => io.parent != null && io.parent.isInstanceOf[Suffixable]).zipWithIndex
        .foreach { case (io, i) => portIndex.put(io, i) }
    }
    sigList.foreach { bt =>
      if (!generated(bt) && LocName.pattern.matcher(bt.getName()).matches() && !bt.isReg && !bt.isInput && !bt.isOutput)
        warn("signal named like a Spinal line name (when_/switch_..._lNN) but not named by Spinal: compared by its name")
      val c = bt.component
      // A bundle field defined in another file (MicroOp's fields) is reported where its bundle/Vec is
      // declared in this design (`Reg(Vec(new MicroOp))` in lsu.scala); inline bundles keep the field line.
      val (f, l) = {
        val own  = loc(bt)
        val root = rootOf(bt)
        if (root eq bt) own else {
          val r = loc(root)
          if (r._1 != null && r._1 != own._1) r else own
        }
      }
      val dir = if (bt.isInput) "in" else if (bt.isOutput) "out" else if (bt.isInOut) "inout" else null
      tSig.add(sigId.get(bt), compId.get(c), areaOf(rootOf(bt).getRefOwnersChain(), c), bt.getName(), rtlPath(bt), spinalPath(bt),
        if (bt.isReg) "reg" else "wire", dir, typeName(bt), width(bt), dataType(bt),
        if (bt.isReg) clockDomainId(bt.clockDomain) else null, resetValue.get(bt), cdRole.get(bt),
        generated(bt), pruned.contains(bt), signalTags(bt), portIndex.get(bt), f, l)
    }
    readStates.foreach { r =>
      // '$' is legal in RTL identifiers; angle brackets are reserved for these database-only nodes.
      val name = s"<mem_read:${r.id}>"
      val path = (instPath(r.comp) :+ name).mkString(".")
      val (f, l) = loc(r.port)
      tSig.add(r.id, compId.get(r.comp), null, name, path, null, "mem_read", null, "Bits", r.width,
        "Bits", clockDomainId(r.cd), null, null, true, false, null, null, f, l)
    }
    writeBundles(db, sigList)

    val tMem = db.table("memories", "id", "signal_id", "component_id", "name", "path", "width", "depth", "technology",
      "init_sha256", "init_words", "key", "file_id", "line")
    memList.foreach { m =>
      val c = m.component
      val (f, l) = loc(m)
      tSig.add(memSig.get(m), compId.get(c), areaOf(m.getRefOwnersChain(), c),
        m.getName(), memPath(m), memPath(m), "mem", null, "Mem", m.width, null, null, null, null, false, false, null, null, f, l)
      // Initial contents (ROMs, initialized RAMs) as a hash of the words, so `diff` sees changed contents.
      val init = Option(m.initialContent)
      val initHash = init.map { words =>
        val md = java.security.MessageDigest.getInstance("SHA-256")
        md.update(s"${m.width}:".getBytes("UTF-8"))
        val keys = words.map(KeyEnc.integerHex)
        keys.foreach(w => md.update(KeyEnc.framed(w).getBytes("UTF-8")))
        (if (keys.exists(ExprText.isIncomplete)) "$incomplete:memory init " else "") +
          md.digest().map(b => f"${b & 0xff}%02x").mkString
      }.orNull
      // Every behavior field of the Mem (allow-list: a field this does not write makes the key incomplete).
      val handled = Set("wordType", "wordCount", "preventMemToBlackboxTranslation", "forceMemToBlackboxTranslation", "_widths",
        "width", "technology", "getWidth", "initialContent", "addressType", "dlcHead", "dlcLast", "component")
      val unmodelled = ExprText.params(m.getClass).filterNot(handled).filterNot(Extractor.MemInfra)
      val memKey = (if (!LibraryClasses.exact(m.getClass, classOf[Mem[_]]) ||
        !LibraryClasses.exact(m.wordType.getClass, classOf[HardType[_]]) || unmodelled.nonEmpty)
        s"$$incomplete:mem ${m.getClass.getName} ${unmodelled.toSeq.sorted.mkString(",")} " else "") +
        s"words=${m.wordCount} width=${m.width} layout=${m._widths.mkString(",")} address=${m.addressWidth} " +
        s"technology=${Option(m.technology).map(t => if (LibraryClasses.isSpinal(t.getClass)) KeyEnc.str(t.technologyKind) else "$incomplete:memory technology").orNull} blackbox=${m.forceMemToBlackboxTranslation}/" +
        s"${SpinalApi.preventBlackbox(m)} init=${initHash}" + Option(tagsText(m.getTags())).map(" tags " + _).getOrElse("")
      tMem.add(memId.get(m), memSig.get(m), compId.get(c), m.getName(), memPath(m), m.width, m.wordCount,
        Option(m.technology).map(_.technologyKind).orNull, initHash, init.map(a => Int.box(a.length)).orNull, memKey, f, l)
    }

  }

  private def writeBundles(db: DbWriter, sigList: Seq[BaseType]): Unit = {
    // ---- bundles: every composite Data (Bundle, Vec, Stream, ...) owning a signal, with its Spinal path
    final class BundleAcc(val id: Int, val comp: Component, val path: String, val data: Data) {
      var parent: Integer = null
      val dirs = mutable.HashSet[String]()
      var signals, bits = 0
    }
    val bundles = new java.util.IdentityHashMap[Data, BundleAcc]()
    val bundleOrder = ArrayBuffer[BundleAcc]()
    sigList.filter(hasSpinalPath).foreach { bt =>
      val segs = spinalPath(bt).split('.')
      var child: BundleAcc = null
      var d: Data = bt.parent
      var k = 1
      while (d != null && k < segs.length) {
        var acc = bundles.get(d)
        val isNew = acc == null
        if (isNew) {
          acc = new BundleAcc(bundleOrder.size + 1, bt.component, segs.dropRight(k).mkString("."), d)
          bundles.put(d, acc); bundleOrder += acc
        }
        if (child != null && child.parent == null) child.parent = acc.id
        if (!pruned.contains(bt)) {
          acc.signals += 1; acc.bits += width(bt)
          acc.dirs += (if (bt.isInput) "in" else if (bt.isOutput) "out" else if (bt.isInOut) "inout" else "internal")
        }
        child = acc
        d = d.parent; k += 1
      }
    }
    val tBundle = db.table("bundles", "id", "component_id", "parent_id", "path", "class_name", "direction", "signals", "bits", "file_id", "line")
    bundleOrder.foreach { b =>
      val (f, l) = loc(b.data)
      val dir = if (b.dirs.isEmpty) null else if (b.dirs.size == 1) b.dirs.head else if (b.dirs.contains("internal")) "mixed" else "in/out"
      tBundle.add(b.id, compId.get(b.comp), b.parent, b.path, b.data match {
        case v: Vec[_] => s"Vec(${v.length})"
        case other     => className(other)
      }, dir, b.signals, b.bits, f, l)
    }

  }

  private def writeBlackBoxes(db: DbWriter, components: Seq[Component]): Unit = {
    val tBb = db.table("blackboxes", "component_id", "generics", "rtl_paths", "body_sha256", "body_from", "key")
    components.foreach {
      case bb: BlackBox if bb.isBlackBox =>
        val (g, paths, body, from, k) = blackboxRow(bb)
        tBb.add(compId.get(bb), g, paths, body, from, k)
      case _ =>
    }

  }

  private def writeArtifacts(db: DbWriter): Unit = {
    // ---- artifacts of the other tools, from this same elaboration
    val tArt = db.table("artifacts", "name", "media_type", "encoding", "size", "content")
    def artifact(name: String, media: String, bytes: Array[Byte]): Unit = {
      val bo = new ByteArrayOutputStream()
      val gz = new GZIPOutputStream(bo)
      gz.write(bytes); gz.close()
      tArt.add(name, media, "gzip", bytes.length, bo.toByteArray)
    }
    def timed(what: String)(f: => Unit): Unit = {
      val t = System.nanoTime()
      try f catch { case NonFatal(e) => warn(s"$what failed: $e"); opts.log(s"$what failed: $e") }
      opts.log(f"$what in ${(System.nanoTime() - t) / 1e9}%.1f s")
    }
    if (opts.pdg) timed("SpinalTrace PDG") {
      val pdg = PdgExtractor.extract(report, ExtractOptions(sourceRoots = opts.sourceRoots.map(_.toFile)))
      if (opts.pdgTables) {
        val tV = db.table("pdg_vertices", "id", "name", "kind", "clocked", "module_path", "assigns_to", "file_id", "line")
        pdg.vertices.zipWithIndex.foreach { case (v, i) =>
          tV.add(i, v.name, v.kind, v.clocked, v.modulePath.mkString("."), v.assignsTo.orNull, fileId(v.loc.file),
            if (v.loc.line > 0) Int.box(v.loc.line) else null)
        }
        val tE = db.table("pdg_edges", "src", "dst", "kind", "clocked")
        pdg.edges.foreach(e => tE.add(e.from, e.to, e.kind, e.clocked))
      }
      pdg.meta.warnings.foreach(w => warn(s"pdg: $w"))
      artifact("pdg.json", "application/json", ujson.write(PdgModel.toJson(pdg)).getBytes("UTF-8"))
    }
    if (opts.blocks) timed("SpinalBlocks diagram") {
      artifact("blocks.json", "application/json", ujson.write(spinalblocks.SpinalBlocks.extract(top, opts.sourceRoots)).getBytes("UTF-8"))
    }
    if (opts.hgldd) timed("SpinalWaves HGLDD") {
      val dir = Files.createTempDirectory("spinaldb-hgldd-")
      val f   = HglddEmitter.emit(report, dir, opts.sourceRoots)
      artifact(s"hgldd/${f.getFileName}", "application/json", Files.readAllBytes(f))
      Files.delete(f); Files.delete(f.getParent); Files.delete(f.getParent.getParent); Files.delete(dir)
    }

  }

  private def writeMetadata(db: DbWriter): Unit = {
    val tInputs = db.table("input_files", "path", "resolved", "sha256", "size", "record")
    ujson.read(inputCapture).obj.get("files").foreach(_.arr.foreach { r =>
      tInputs.add(r("source").str, r("resolved").str, r("sha256").str, r("size").num.toLong, ujson.write(r))
    })
    val tFiles = db.table("files", "id", "path")
    files.foreach { case (p, id) => tFiles.add(id, p) }
    val tWarn = db.table("warnings", "source", "message")
    warnings.foreach { case (m, n) =>
      val (src, msg) = if (m.startsWith("pdg: ")) ("pdg", m.stripPrefix("pdg: ")) else ("spinaldb", m)
      tWarn.add(src, if (n > 1) s"$msg (x$n)" else msg)
    }
    val tMeta = db.table("meta", "key", "value")
    (Seq(
      "schema" -> Schema.Version,
      "generator" -> "spinaldb 0.1.0",
      "spinalhdl" -> Spinal.version,
      "emission_config" -> EmissionConfig.key(report),
      "input_capture" -> inputCapture,
      "toplevel" -> top.definitionName,
      "toplevel_class" -> top.getClass.getName,
      "extra_scopes" -> s"TOP ${top.definitionName}",
      "created" -> java.time.Instant.now().toString,
      "source_roots" -> opts.sourceRoots.map(_.toAbsolutePath.normalize.toString).mkString(java.io.File.pathSeparator),
      "pdg_naming_phase" -> opts.pdg.toString,
      "pdg_tables" -> opts.pdgTables.toString
    ) ++ opts.meta).foreach { case (k, v) => tMeta.add(k, v) }
  }

  def write(db: DbWriter): Unit = {
    val t0 = System.nanoTime()
    val components = ArrayBuffer[Component]()
    def walkC(c: Component): Unit = { components += c; c.children.foreach(walkC) }
    walkC(top)
    captureInputs(components.toSeq)
    collectClockSignals(components.toSeq)

    val tComp = db.table("components", "id", "parent_id", "path", "name", "module", "class_name", "blackbox", "depth", "file_id",
      "line", "tags")
    val compRows = ArrayBuffer[() => Unit]()
    components.foreach { c =>
      val id = compId.size + 1
      compId.put(c, id)
      val (f, l) = componentLoc(c)
      val path = instPath(c)
      // Written once generated registers have their ids (`text.prepare`): a tag may hold a clock domain.
      compRows += (() => tComp.add(id, if (c.parent == null) null else compId.get(c.parent), path.mkString("."),
        if (c.parent == null) c.definitionName else c.getName(), c.definitionName, className(c),
        c.isInstanceOf[BlackBox] && c.asInstanceOf[BlackBox].isBlackBox, path.length, f, l, componentTags(c)))
    }

    // Signal and memory ids first, so statements can reference anything in any component.
    val sigList = ArrayBuffer[BaseType]()
    val memList = ArrayBuffer[Mem[_]]()
    var nextSig = 0
    components.foreach { c =>
      c.dslBody.walkDeclarations {
        case bt: BaseType if !sigId.containsKey(bt) => nextSig += 1; sigId.put(bt, nextSig); sigList += bt
        case m: Mem[_] if !memSig.containsKey(m)    => nextSig += 1; memSig.put(m, nextSig); memList += m
        case _                                      =>
      }
    }
    opts.log(s"${components.size} components, ${sigList.size} signals, ${memList.size} memories")

    val walker = new StatementWalker(db, nextSig)

    // Generated registers get their ids before any key is written, so equal-content registers are ranked
    // in declaration order (ExprText.prepare).
    text.prepare(sigList.filter(bt => bt.isReg && generated(bt) && !pruned.contains(bt)).toSeq)
    compRows.foreach(_())

    // Memories need ids before the walk (mem ports reference them).
    memList.zipWithIndex.foreach { case (m, i) => memId.put(m, i + 1) }

    walker.write(components.toSeq)

    writeSignalsAndMemories(db, components.toSeq, sigList.toSeq, memList.toSeq, walker.resetValue, walker.readStates.toSeq)
    writeBlackBoxes(db, components.toSeq)

    val tEdge = db.table("edges", "src", "dst", "kind")
    walker.edges.forEach { k =>
      val v = k.longValue
      tEdge.add((v >>> 32).toInt, ((v >>> 3) & 0x1fffffffL).toInt, walker.kindName((v & 7).toInt))
    }

    val tCd = db.table("clock_domains", "id", "clock", "reset", "reset_kind", "reset_active_high", "clock_enable", "soft_reset", "clock_edge",
      "clock_enable_active_high", "soft_reset_active_high", "clock_key", "reset_key", "clock_enable_key", "soft_reset_key")
    cdIds.foreach { case (r, id) =>
      tCd.add(id, r.clock, r.reset, r.resetKind, r.resetHigh, r.enable, r.soft, r.edge, r.enableHigh, r.softHigh,
        r.clockKey, r.resetKey, r.enableKey, r.softKey) }

    // Additive: the declared frequency of each clock domain (Spinal `FixedFrequency`), for SDC intent.
    val tFreq = db.table("clock_frequencies", "clock_domain_id", "hz")
    val freqs = mutable.LinkedHashSet[(Int, String)]()
    cdOf.forEach { (cd, id) =>
      cd.frequency match {
        case f: ClockDomain.FixedFrequency => freqs += ((id.intValue, f.getValue.toBigDecimal.bigDecimal.toPlainString))
        case _ =>
      }
    }
    freqs.foreach { case (id, hz) => tFreq.add(id, hz) }

    val tRtl = db.table("rtl_files", "path")
    (report.generatedSourcesPaths ++ report.rtlSourcesPaths).toSeq.distinct.sorted.foreach(p => tRtl.add(new File(p).getAbsolutePath))
    opts.log(f"netlist tables in ${(System.nanoTime() - t0) / 1e9}%.1f s")

    writeArtifacts(db)
    writeMetadata(db)
    opts.log(f"extraction done in ${(System.nanoTime() - t0) / 1e9}%.1f s")
  }
}

object Extractor {
  /** Tags that Spinal or our own tools add for elaboration bookkeeping and that never change the
    * generated hardware. Audited against SpinalHDL 1.15.0; any other tag is compared. */
  val IgnoredTags: Set[Class[_]] = Set(
    classOf[GenericValue],                    // generic payload is compared in `blackboxes.generics`
    classOf[DefaultTag],                      // PhaseApplyIoDefault already made its assignment
    allowAssignmentOverride.getClass,         // elaboration check switch (allow `:=` twice)
    AllowPartialyAssignedTag.getClass,        // elaboration check switch (partly assigned memory words)
    unusedTag.getClass,                       // silences the pruned-signal report
    spinaltrace.SpinalTraceNamedTag.getClass,
    spinaltrace.SpinalGeneratedNameTag.getClass
  )

  /** Spinal's own clock-domain role tag classes (a user subclass is not one of them). */
  val RoleTags: Set[Class[_]] = Set(classOf[ClockTag], classOf[ResetTag], classOf[ClockEnableTag])

  /** The signal a clock-domain role tag (`ClockTag`, `ResetTag`, `ClockEnableTag`) says it is on. */
  def roleSignal(t: ClockDomainBoolTag): Bool = t match {
    case ClockTag(cd)       => cd.clock
    case ResetTag(cd)       => cd.reset
    case ClockEnableTag(cd) => cd.clockEnable
  }

  /** Payload fields are keyed; compiler bookkeeping is omitted. */
  sealed trait FieldRole
  object FieldRole {
    case object Payload  extends FieldRole
    case object Compiler extends FieldRole
  }

  private val Bitmap      = "bitmap\\$(?:trans\\$|init\\$)?\\d+".r
  private val BitmapTypes = Set[Class[_]](java.lang.Boolean.TYPE, java.lang.Byte.TYPE, java.lang.Short.TYPE, java.lang.Integer.TYPE, java.lang.Long.TYPE)

  /** Match the Scala 2.13 compiler's exact name, modifiers and field type. */
  def fieldRole(f: java.lang.reflect.Field): FieldRole = {
    import java.lang.reflect.Modifier._
    val n: String   = f.getName
    val m: Int      = f.getModifiers
    val c: Class[_] = f.getDeclaringClass
    val shaped = n match {
      case "MODULE$"          => isPublic(m) && isStatic(m) && isFinal(m) && f.getType == c
      case "serialVersionUID" => isPrivate(m) && isStatic(m) && isFinal(m) && f.getType == java.lang.Long.TYPE
      case Bitmap()           => isPrivate(m) && isVolatile(m) && !isFinal(m) && BitmapTypes(f.getType) &&
        isTransient(m) == n.startsWith("bitmap$trans$")
      case _                  => false
    }
    if (shaped) FieldRole.Compiler else FieldRole.Payload
  }

  /** Constant final vals have no field. Read their values from Scala signatures. */
  final case class ScalaSig(constants: Seq[(String, Any)])

  private val sigs = new java.util.concurrent.ConcurrentHashMap[Class[_], Option[ScalaSig]]()

  def scalaSig(c: Class[_]): Option[ScalaSig] = sigs.computeIfAbsent(c, (k: Class[_]) => readSig(k))

  /** scala-reflect's first read of a class that refers to `spinal.core` can fail with `assertion failed:
    * Bool` (the package holds a class and a method of that name); a second read of the same class then
    * succeeds with every declaration, those of mixed-in traits included (measured with SpinalHDL 1.15.0
    * and Scala 2.13.14). So two attempts; a read where a class or trait it inherits has no class type
    * counts as failed. */
  private def readSig(c: Class[_]): Option[ScalaSig] = readSigOnce(c).orElse(readSigOnce(c))

  private def readSigOnce(c: Class[_]): Option[ScalaSig] = try {
    import scala.reflect.runtime.{universe => ru}
    val sym   = ru.runtimeMirror(c.getClassLoader).classSymbol(c)
    val bases = sym.baseClasses
    def classType(t: ru.Type): Boolean = t match {
      case _: ru.ClassInfoTypeApi => true
      case p: ru.PolyTypeApi      => classType(p.resultType)
      case _                      => false
    }
    def name(s: ru.Symbol) = s.name.encodedName.toString.trim // a field's own symbol ends with a space
    def const(t: ru.Type): Option[Any] = t match {
      case k: ru.ConstantTypeApi          => Some(k.value.value)
      case r: ru.NullaryMethodTypeApi     => const(r.resultType)
      case _                       => None
    }
    if (bases.isEmpty || !bases.forall(b => classType(b.info))) None
    else {
      val constants = bases.filterNot { b =>
        // Scala's Any/AnyRef have no JVM class. Do not exclude anything without origin evidence.
        scala.util.Try(ru.runtimeMirror(c.getClassLoader).runtimeClass(b.asClass)).toOption
          .exists(cls => LibraryClasses.isScala(cls) || LibraryClasses.isJdk(cls))
      }
        .flatMap(_.info.decls.filter(_.isTerm).flatMap(d => const(d.info).map(name(d) -> _)))
      // A name is a constant once (its getter and its field symbol both carry the value); a subclass's
      // constant comes before an inherited one of the same name (`baseClasses` starts with the class).
      val seen = mutable.LinkedHashMap[String, Any]()
      constants.foreach { case (k, v) => if (!seen.contains(k)) seen(k) = v }
      Some(ScalaSig(seen.toSeq.sortBy(_._1)))
    }
  } catch { case NonFatal(_) | _: LinkageError => None }

  /** Mem fields from Spinal's naming, scoping and statement bookkeeping. */
  val MemInfra: Set[String] = Set("_spinalTags", "spinal$core$Nameable$$mode", "refOwner", "nameableRef", "namePriority",
    "name", "parentScope", "lastScopeStatement", "nextScopeStatement", "instanceCounter", "scalaTrace", "globalData",
    "algoInt", "algoIncremental", "dlcHead", "dlcLast")
}
