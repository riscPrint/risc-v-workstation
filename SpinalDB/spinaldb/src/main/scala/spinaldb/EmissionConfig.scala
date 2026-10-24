package spinaldb

import java.lang.reflect.Modifier
import spinal.core._
import spinal.core.internals.PhaseDeviceDefault
import scala.collection.{immutable, mutable}
import scala.util.control.NonFatal

/** Effective emission settings plus compiled code and state for user hooks. Unknown values keep
  * an incomplete marker outside hashes. No user formatter, iterator or payload method is used. */
object EmissionConfig {
  private val reports = new java.util.WeakHashMap[SpinalReport[_ <: Component], String]()
  private val ignored = Set("targetDirectory", "netlistFileName", "oneFilePerComponent", "debugComponents",
    "verbose", "genLineComments", "headerWithDate", "headerWithRepoHash", "printFilelist")
  private val hooks = Set("phasesInserters", "transformationPhases", "memBlackBoxers")
  private val records: Set[Class[_]] = Set(classOf[ClockDomainConfig], classOf[Device],
    classOf[ObfuscateConfig], classOf[DumpWaveConfig], classOf[ClockDomain.UnknownFrequency],
    classOf[ClockDomain.FixedFrequency])
  private val labels: Seq[AnyRef] = Seq(Verilog, SystemVerilog, VHDL, RISING, FALLING, ASYNC, SYNC,
    BOOT, HIGH, LOW, GenerationFlags.synthesis, GenerationFlags.simulation, GenerationFlags.formal)
  private val smallSets: Set[Class[_]] = (0 to 4).map(n => immutable.Set.from(0 until n).getClass).toSet
  private val smallMaps: Set[Class[_]] = (0 to 4).map(n => immutable.Map.from((0 until n).map(i => i -> i)).getClass).toSet
  private val tupleClass = "scala.Tuple(?:[1-9]|1[0-9]|2[0-2])(?:\\$mc[A-Z]+\\$sp)?".r
  private def incomplete(v: Any): String =
    "$incomplete:emission config " + (if (v == null) "null" else KeyEnc.name(v.getClass.getName))

  private[spinaldb] final class Session(config: SpinalConfig) {
    private val code = new CodeCapture
    private val active = new java.util.IdentityHashMap[AnyRef, java.lang.Boolean]()
    private def fields(v: AnyRef, excluded: Set[String] = Set.empty, inherited: Boolean = false): String = {
      val classes = Iterator.iterate[Class[_]](v.getClass)(_.getSuperclass).takeWhile(c => c != null && c != classOf[Object])
      val fs = (if (inherited) classes.toSeq else Seq(v.getClass)).flatMap(_.getDeclaredFields)
        .filterNot(f => Modifier.isStatic(f.getModifiers) || excluded(f.getName))
        .sortBy(f => (f.getDeclaringClass.getName, f.getName))
      fs.map { f =>
        val k = try { f.setAccessible(true); value(f.get(v)) } catch { case NonFatal(_) => incomplete(v) }
        KeyEnc.name(if (inherited) f.getDeclaringClass.getName + "." + f.getName else f.getName) + "=" + KeyEnc.framed(k)
      }.mkString(KeyEnc.name(v.getClass.getName) + "{", ",", "}")
    }
    private def guarded(v: AnyRef)(body: => String): String = {
      if (active.containsKey(v) || active.size >= 64) return incomplete(v)
      active.put(v, true)
      try body finally active.remove(v)
    }
    // These are strict library implementations. Lazy values, views and default callbacks need
    // more state than their elements. Never invoke iteration on a user subclass.
    private def strictSeq(x: immutable.Seq[_]): Boolean = x match {
      case _: List[_] | _: Vector[_] | _: immutable.Queue[_] | _: immutable.ArraySeq[_] => true
      case _ => false
    }
    private def plainSet(x: immutable.Set[_]): Boolean = smallSets(x.getClass) || (x match {
      case _: immutable.HashSet[_] | _: immutable.ListSet[_] | _: immutable.BitSet => true
      case _ => false
    })
    private def plainMap(x: immutable.Map[_, _]): Boolean = smallMaps(x.getClass) || (x match {
      case _: immutable.HashMap[_, _] | _: immutable.ListMap[_, _] | _: immutable.VectorMap[_, _] => true
      case _ => false
    })
    private def elements(x: AnyRef, items: Iterator[Any], extra: String = ""): String = guarded(x) {
      KeyEnc.name(x.getClass.getName) + extra + items.map(a => KeyEnc.framed(value(a))).mkString("[", ",", "]")
    }
    private def entries(x: immutable.Map[_, _], extra: String = ""): String = guarded(x) {
      KeyEnc.name(x.getClass.getName) + extra + x.iterator.map { case (k, a) =>
        KeyEnc.framed(value(k)) + KeyEnc.framed(value(a))
      }.mkString("{", ",", "}")
    }
    private def user(v: AnyRef): String = guarded(v) {
      try code.lambda(v) match {
        case Some((identity, args)) => identity + args.map(a => KeyEnc.framed(value(a))).mkString("[", ",", "]")
        case None =>
          val c = v.getClass
          // Unknown library/JDK values are still unsupported. Their internals are not a contract.
          if (LibraryClasses.isJdk(c) || LibraryClasses.isScala(c) || LibraryClasses.isSpinal(c) ||
            LibraryClasses.isSpinalLib(c) || LibraryClasses.isSpinalDsl(c)) incomplete(v)
          else {
            val classes = Iterator.iterate[Class[_]](c)(_.getSuperclass).takeWhile(k => k != null && k != classOf[Object])
              .map(code.classKey).map(KeyEnc.framed).mkString("[", ",", "]")
            classes + fields(v, inherited = true)
          }
      } catch { case NonFatal(_) | _: LinkageError => incomplete(v) }
    }
    private def value(v: Any): String = KeyEnc.scalar(v).getOrElse(v match {
      case r: AnyRef if labels.exists(_ eq r) => KeyEnc.label(r)
      case r: AnyRef if r eq PhaseDeviceDefault => "PhaseDeviceDefault"
      case r: AnyRef if records(r.getClass) && LibraryClasses.isSpinal(r.getClass) => fields(r)
      case x: HertzNumber if LibraryClasses.exact(x.getClass, classOf[HertzNumber]) =>
        KeyEnc.scalar(x.toBigDecimal).getOrElse(incomplete(x))
      case x: AnyRef if x.getClass.isArray =>
        // JVM array classes cannot be subclassed. Reflection reads primitive and reference
        // elements without a user iterator. The class name retains the component type.
        elements(x, (0 until java.lang.reflect.Array.getLength(x)).iterator.map(i => java.lang.reflect.Array.get(x, i)))
      case x: mutable.HashSet[_] if LibraryClasses.exact(x.getClass, classOf[mutable.HashSet[_]]) =>
        guarded(x) { x.toSeq.map(value).sorted.map(KeyEnc.framed).mkString("set{", ",", "}") }
      case x: mutable.ArrayBuffer[_] if LibraryClasses.exact(x.getClass, classOf[mutable.ArrayBuffer[_]]) =>
        guarded(x) { x.map(a => KeyEnc.framed(value(a))).mkString("[", ",", "]") }
      case x: mutable.LinkedHashMap[_, _] if LibraryClasses.exact(x.getClass, classOf[mutable.LinkedHashMap[_, _]]) =>
        guarded(x) { x.toSeq.map { case (k, a) => KeyEnc.framed(value(k)) + KeyEnc.framed(value(a)) }.mkString("{", ",", "}") }
      case x: immutable.Range if LibraryClasses.isScala(x.getClass) =>
        // The bounds and step remain observable even for empty or one-element ranges.
        KeyEnc.name(x.getClass.getName) + Seq(x.start, x.end, x.step, x.isInclusive)
          .map(a => KeyEnc.framed(value(a))).mkString("[", ",", "]")
      case x: immutable.Seq[_] if LibraryClasses.isScala(x.getClass) && strictSeq(x) =>
        elements(x, x.iterator)
      case x: immutable.TreeSet[_] if LibraryClasses.exact(x.getClass, classOf[immutable.TreeSet[_]]) =>
        elements(x, x.iterator, KeyEnc.framed(value(x.ordering)))
      case x: immutable.Set[_] if LibraryClasses.isScala(x.getClass) && plainSet(x) =>
        elements(x, x.iterator)
      case x: immutable.TreeMap[_, _] if LibraryClasses.exact(x.getClass, classOf[immutable.TreeMap[_, _]]) =>
        entries(x, KeyEnc.framed(value(x.ordering)))
      case x: immutable.Map[_, _] if LibraryClasses.isScala(x.getClass) && plainMap(x) => entries(x)
      case x: Option[_] if LibraryClasses.exact(x.getClass, classOf[Some[_]]) || LibraryClasses.exact(x.getClass, None.getClass) =>
        elements(x, x.iterator)
      case x: Product if LibraryClasses.isScala(x.getClass) && tupleClass.matches(x.getClass.getName) =>
        elements(x.asInstanceOf[AnyRef], x.productIterator)
      case x: Ordering[_] if LibraryClasses.isScala(x.getClass) => guarded(x) { fields(x, inherited = true) }
      case x: scala.collection.Iterable[_] => incomplete(x)
      case r: AnyRef => user(r)
      case _ => incomplete(v)
    })
    // Read the user lists before SpinalDB and Spinal add their own phases or mutate phase state.
    private val userHooks = hooks.toSeq.sorted.map { name =>
      val f = classOf[SpinalConfig].getDeclaredField(name); f.setAccessible(true)
      " " + name + "=" + value(f.get(config))
    }.mkString
    // Capture code for all original payloads before elaboration, not only the phase lists.
    // Later-created payloads can use the already captured classpath, never a new live entry.
    fields(config, ignored ++ hooks)
    code.seal()
    private val configClass = if (LibraryClasses.exact(config.getClass, classOf[SpinalConfig])) "[]" else incomplete(config)
    def key(report: SpinalReport[_ <: Component]): String = {
      val effective = report.globalData.config
      val k = if (!LibraryClasses.exact(effective.getClass, classOf[SpinalConfig])) incomplete(effective)
        else fields(effective, ignored ++ hooks) + " configClass=" + configClass + userHooks
      if (code.unchanged) k else k + " $incomplete:emission config compiled classpath changed"
    }
  }
  private[spinaldb] def capture(config: SpinalConfig): Session = new Session(config)
  private[spinaldb] def remember(report: SpinalReport[_ <: Component], session: Session): Unit = synchronized {
    reports.put(report, session.key(report))
  }
  def key(report: SpinalReport[_ <: Component]): String = synchronized {
    Option(reports.get(report)).getOrElse("$incomplete:emission config report not made by SpinalDB.elaborate")
  }
}
