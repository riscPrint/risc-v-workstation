package spinaldb

import spinal.core._
import spinal.core.internals._

/** Renders Spinal expressions as short, readable text for the database (`source`, `expr` columns).
  *
  * Signals are written by their RTL path relative to the component the statement lives in (`x`,
  * `child.io_out`), the same names `rvw query` resolves. Compiler-generated temporaries (`_zz_*`,
  * `when_File_l12`) with a single full driver are inlined, so `when(when_Gcd_l21)` reads as
  * `when(x > y)`. Text longer than `maxLen` is cut with `…`. */
class ExprText(nameOf: (BaseType, Component) => String, generated: BaseType => Boolean, maxLen: Int = 400,
               domainOf: BaseType => String = _ => "-", loopLimit: Int = ExprText.LoopLimit,
               cdRawOf: ClockDomain => String = cd => if (cd == null) "-" else "cd?",
               tagsOf: BaseType => String = _ => null) {

  private def soleDriver(bt: BaseType): Option[Expression] =
    if (bt.isReg || bt.isInput || bt.isOutput || bt.isInOut || !generated(bt)) None
    else {
      var n = 0
      var src: Expression = null
      var ok = true
      bt.foreachStatements {
        case a: DataAssignmentStatement if (a.target eq bt) && (a.parentScope eq bt.rootScopeStatement) => n += 1; src = a.source
        case _ => ok = false
      }
      if (ok && n == 1) Some(src) else None
    }

  def render(e: Expression, from: Component): String = {
    val sb = new StringBuilder
    go(e, from, sb, 0)
    val s = if (sb.length > maxLen) sb.substring(0, maxLen) + "…" else sb.toString
    stripOuter(s)
  }

  /** `(a + b)` -> `a + b` when the outer brackets enclose everything. */
  private def stripOuter(s: String): String = {
    if (s.length < 2 || s.head != '(' || s.last != ')') return s
    var d = 0
    var i = 0
    while (i < s.length - 1) {
      if (s(i) == '(') d += 1 else if (s(i) == ')') d -= 1
      if (d == 0) return s
      i += 1
    }
    s.substring(1, s.length - 1)
  }

  private def op(opName: String): Option[(String, Int)] = {
    val t = opName.split(' ')
    if (t.length == 3 && t(0).headOption.exists(_.isUpper)) Some((t(1), 2))
    else if (t.length == 2 && !t(0).head.isLetterOrDigit) Some((t(0), 1))
    else None
  }

  private def lit(l: Literal): String = l match {
    case b: BoolLiteral   => if (b.value) "True" else "False"
    case e: EnumLiteral[_] => s"${e.senum.spinalEnum.getName("enum")}.${e.senum.getName()}"
    case other =>
      val v = try other.getValue() catch { case _: Throwable => null }
      if (v == null) "DontCare" else if (v >= 0 && v < 10) v.toString else if (v < 0) v.toString else "0x" + v.toString(16)
  }

  private def go(e: Expression, from: Component, sb: StringBuilder, depth: Int): Unit = {
    if (sb.length > maxLen) return
    if (depth > 24) { sb ++= "…"; return }
    def rec(x: Expression): Unit = go(x, from, sb, depth + 1)
    e match {
      case bt: BaseType =>
        soleDriver(bt) match {
          case Some(d) if depth < 12 => rec(d) // operators and muxes bracket themselves
          case _ => sb ++= nameOf(bt, from)
        }
      case l: Literal => sb ++= lit(l)
      case c: Cast    => rec(c.input)
      case r: Resize  => rec(r.input)
      case a: BitVectorBitAccessFixed      => rec(a.source); sb ++= s"(${a.bitId})"
      case a: BitVectorBitAccessFloating   => rec(a.source); sb += '('; rec(a.bitId); sb += ')'
      case a: BitVectorRangedAccessFixed   => rec(a.source); sb ++= s"(${a.hi} downto ${a.lo})"
      case a: BitVectorRangedAccessFloating => rec(a.source); sb += '('; rec(a.offset); sb ++= s", ${a.size} bits)"
      case m: BinaryMultiplexer =>
        sb += '('; rec(m.cond); sb ++= " ? "; rec(m.whenTrue); sb ++= " : "; rec(m.whenFalse); sb += ')'
      case m: Multiplexer =>
        sb ++= "mux("; rec(m.select)
        m.inputs.foreach { i => sb ++= ", "; rec(i) }
        sb += ')'
      case r: MemReadAsync      => sb ++= memName(r.mem, from); sb += '('; rec(r.address); sb += ')'
      case r: MemReadSync       => sb ++= memName(r.mem, from); sb ++= ".readSync("; rec(r.address); sb += ')'
      case r: MemReadWrite      => sb ++= memName(r.mem, from); sb ++= ".readWrite("; rec(r.address); sb += ')'
      case r: MemReadAsyncWrite => sb ++= memName(r.mem, from); sb += '('; rec(r.address); sb += ')'
      case s: Operator.BitVector.ShiftRightByInt => rec(s.source); sb ++= s" >> ${s.shift}"
      case s: Operator.BitVector.ShiftLeftByInt  => rec(s.source); sb ++= s" << ${s.shift}"
      case b: BinaryOperator =>
        op(b.opName) match {
          case Some((o, 2)) => sb += '('; rec(b.left); sb ++= s" $o "; rec(b.right); sb += ')'
          case _            => sb ++= b.opName.takeWhile(_ != ' '); sb += '('; rec(b.left); sb ++= ", "; rec(b.right); sb += ')'
        }
      case u: UnaryOperator =>
        op(u.opName) match {
          case Some((o, 1)) => sb ++= o; rec(u.source)
          case _            => sb ++= u.opName; sb += '('; rec(u.source); sb += ')'
        }
      case other =>
        val name = other match {
          case n: Operator => n.opName
          case _           => other.getClass.getSimpleName
        }
        sb ++= name; sb += '('
        var first = true
        other.foreachExpression { x => if (!first) sb ++= ", "; first = false; rec(x) }
        sb += ')'
    }
  }

  // ------------------------------------------------------------------ typed key
  /** A complete, typed form of `e` for comparing two elaborations (`assignments.key`, `conds.key`):
    * every node's Spinal class (so signed and unsigned operators differ), width, and constant
    * parameters (shift amounts, resize sizes, bit ranges, literal values); casts and resizes are kept.
    * Compiler temporaries are never keyed by name, because their names change with unrelated edits:
    * one with a single full driver is inlined as in the display text; any other combinational one
    * (a `mux`/`switch` result assigned in several branches) is written `$gen:<type>{...}` with its
    * own assignments in order, each as its condition chain (`when`/`else`/`case`/`default` with
    * typed condition and case keys) and source key.
    *
    * A generated register (`RegNext(x) init k`, unnamed) is written where it is read as
    * `$reg:<hash>#<rank>`. The hash is a canonical hash of its content at any depth: its template
    * `$reg:<type>@<clock domain>{...}` (its own assignments, `init` included, in the same form; the
    * clock domain with the typed keys of its clock, reset, clock-enable and soft-reset signals) with
    * every generated register it reads replaced by that register's id. Outside a register loop that
    * is a Merkle hash. In a loop (a strongly connected set of generated registers) the hash of a
    * member is that of the loop numbered in depth-first order from that member, members written
    * by number and registers outside the loop by id; so `a - b` and `b - a` of two register chains
    * differ at any depth. The rank numbers distinct registers with the same hash (see `assignIds`,
    * `prepare`), so one register read twice and two equal registers are different keys:
    * `(r - r) - s` and `(r - s) - s` differ. Two equal registers that trade places may give a false
    * difference; two different register graphs never give equal keys.
    *
    * Sub-forms longer than 160 characters are replaced by `h:<sha256 prefix>`, so a key stays short
    * but still changes whenever any part of the expression does. Where a key cannot be complete (a
    * combinational loop through temporaries had to be cut, or a register loop is larger than
    * `loopLimit`), it holds `$incomplete:<type>`, and a hash that covers such a part is written
    * `h!:` instead of `h:`, so a reader can tell the key cannot show two designs equal. */
  def key(e: Expression, from: Component): String =
    if (e == null) null else squash(resolve(squash(keyOf(e, from, newVisiting()))))

  private def newVisiting() = new java.util.IdentityHashMap[BaseType, java.lang.Boolean]()

  /** Memo of a temporary's key (raw: generated registers are tokens, so it never depends on context). */
  private val keyMemo = new java.util.IdentityHashMap[BaseType, (Component, String)]()
  private def memo(bt: BaseType, from: Component)(compute: => String): String = {
    val m = keyMemo.get(bt)
    if (m != null && (m._1 eq from)) m._2
    else {
      val v = compute
      if (!ExprText.isIncomplete(v)) keyMemo.put(bt, (from, v))
      v
    }
  }

  // Generated registers in raw keys: `\u0001<n>\u0001`, `n` the register's number in this extraction.
  private val regIds = new java.util.IdentityHashMap[BaseType, Integer]()
  private val regs = scala.collection.mutable.ArrayBuffer[BaseType]()
  private def tokenId(bt: BaseType): Int = {
    var id = regIds.get(bt)
    if (id == null) { id = regs.length; regIds.put(bt, id); regs += bt }
    id
  }
  private def token(bt: BaseType): String = s"\u0001${tokenId(bt)}\u0001"
  private val Token = "\u0001(\\d+)\u0001".r
  private def tokens(s: String): Seq[Int] =
    if (s.indexOf('\u0001') < 0) Nil else Token.findAllMatchIn(s).map(_.group(1).toInt).toSeq.distinct
  private def replaceTokens(s: String)(f: Int => String): String =
    if (s.indexOf('\u0001') < 0) s
    else Token.replaceAllIn(s, m => scala.util.matching.Regex.quoteReplacement(f(m.group(1).toInt)))

  private def sha(s: String): String = {
    val md = java.security.MessageDigest.getInstance("SHA-256").digest(s.getBytes("UTF-8"))
    (if (ExprText.isIncomplete(s)) "h!:" else "h:") + md.take(16).map(b => f"${b & 0xff}%02x").mkString
  }

  /** A long sub-form becomes its hash. Register tokens are hashed by position (`\u0002k`, the k-th
    * distinct register) and listed after the hash, so the hash does not depend on register numbers
    * and `resolve` can still put each register's id in. */
  private def squash(s: String): String =
    if (s.length <= 160) s
    else {
      val ts = tokens(s)
      if (ts.isEmpty) sha(s)
      else {
        val pos = ts.zipWithIndex.toMap
        sha(replaceTokens(s)(t => s"\u0002${pos(t)}")) + ts.map(t => s"\u0001$t\u0001").mkString("[", ",", "]")
      }
    }

  /** `raw` with every register token replaced by `$reg:<id>`. */
  private def resolve(raw: String): String = {
    val pending = tokens(raw).filterNot(ids.contains)
    if (pending.nonEmpty) assignIds(pending)
    replaceTokens(raw)(t => "$reg:" + ids(t))
  }

  /** A typed key whose generated registers stay tokens: for parts of a register's own template (its
    * clock-domain controls), where a register read is an edge of the register graph, not an id. */
  def rawKey(e: Expression, from: Component): String =
    if (e == null) null else squash(keyOf(e, from, newVisiting()))

  /** Numbers `regs` (every generated register of the design, in declaration order) and gives each its
    * id now, so a register's rank among equal-content registers follows declaration order, not the
    * order keys are asked for. Registers found later (outside `regs`) are numbered after them. */
  def prepare(regs: Seq[BaseType]): Unit = assignIds(regs.map(tokenId))

  // Per register: its template (raw, from its own component) and its id.
  private val templates = scala.collection.mutable.HashMap[Int, String]()
  private val ids = scala.collection.mutable.HashMap[Int, String]()
  private def template(r: Int): String = templates.getOrElseUpdate(r, {
    val bt = regs(r)
    // Generated registers can enter directly through prepare, without keyOf.
    if (!LibraryClasses.signal(bt.getClass)) s"$$incomplete:signal ${bt.getClass.getName}"
    else squash(s"$$reg:${typeTag(bt)}@${domainOf(bt)}${tagPart(bt)}{${driversKey(bt, bt.component, newVisiting())}}")
  })
  /** A generated signal's tags and attributes (`tagsOf`), part of its template or key: `#tags[...]`. */
  private def tagPart(bt: BaseType): String = Option(tagsOf(bt)).map(t => s"#tags[$t]").getOrElse("")
  /** How many registers already have each content hash: the next one with that hash gets this rank. */
  private val groupSize = scala.collection.mutable.HashMap[String, Int]()

  /** Ids for every register reachable from `roots` that has none. A register's id is
    * `<content hash>#<rank>`: the content hash is its template with every register it reads written
    * by that register's id (a loop's members by their depth-first number from the member, see
    * `content`), and the rank tells apart distinct registers with equal content, in register-number
    * order. Ids are given level by level (a register's level is above every register it reads), so
    * all registers with one content hash, which have the same level, are ranked together; the
    * labelling keeps sharing: `(r - r) - s` and `(r - s) - s` of two equal registers differ. */
  private def assignIds(roots: Seq[Int]): Unit = {
    // Tarjan's strongly connected components, iteratively (long chains do not overflow the stack);
    // components come out after every component they read.
    val index = scala.collection.mutable.HashMap[Int, Int]()
    val low = scala.collection.mutable.HashMap[Int, Int]()
    val onStack = scala.collection.mutable.HashSet[Int]()
    val stack = scala.collection.mutable.Stack[Int]()
    val sccs = scala.collection.mutable.ArrayBuffer[Seq[Int]]()
    var next = 0
    for (r0 <- roots.distinct.sorted if !ids.contains(r0) && !index.contains(r0)) {
      val work = scala.collection.mutable.Stack[(Int, Int)]((r0, 0))
      while (work.nonEmpty) {
        val (v, i0) = work.pop()
        if (i0 == 0) { index(v) = next; low(v) = next; next += 1; stack.push(v); onStack += v }
        val kids = tokens(template(v))
        var i = i0
        var descended = false
        while (i < kids.length && !descended) {
          val w = kids(i)
          i += 1
          if (!ids.contains(w)) {
            if (!index.contains(w)) { work.push((v, i)); work.push((w, 0)); descended = true }
            else if (onStack(w)) low(v) = math.min(low(v), index(w))
          }
        }
        if (!descended) {
          if (low(v) == index(v)) {
            val scc = scala.collection.mutable.ArrayBuffer[Int]()
            var w = -1
            while (w != v) { w = stack.pop(); onStack -= w; scc += w }
            sccs += scc.toSeq
          }
          if (work.nonEmpty) { val (u, _) = work.top; low(u) = math.min(low(u), low(v)) }
        }
      }
    }
    val sccOf = scala.collection.mutable.HashMap[Int, Int]()
    val level = new Array[Int](sccs.length)
    for ((scc, i) <- sccs.zipWithIndex) {
      scc.foreach(sccOf(_) = i)
      level(i) = scc.flatMap(r => tokens(template(r))).flatMap(sccOf.get).filter(_ != i).map(level(_) + 1).foldLeft(0)(math.max)
    }
    for ((_, members) <- sccs.indices.groupBy(level(_)).toSeq.sortBy(_._1)) {
      for ((r, h) <- members.flatMap(i => content(sccs(i))).sortBy(_._1)) {
        val k = groupSize.getOrElse(h, 0)
        groupSize(h) = k + 1
        ids(r) = s"$h#$k"
      }
    }
  }

  /** Content hash of each register of one strongly connected set; every register outside it they
    * read has an id. In a loop the hash of a member is that of the loop numbered in depth-first
    * order from it, so it does not depend on where a walk started. */
  private def content(scc: Seq[Int]): Seq[(Int, String)] = {
    val members = scc.toSet
    if (scc.size == 1 && !tokens(template(scc.head)).contains(scc.head)) {
      val r = scc.head
      Seq(r -> sha(replaceTokens(template(r))(t => "$reg:" + ids(t))))
    } else if (scc.size > loopLimit) {
      for (r <- scc) yield r -> sha(s"$$incomplete:loop of ${scc.size} registers;" + replaceTokens(template(r))(t =>
        if (members(t)) "@" else "$reg:" + ids(t)))
    } else {
      for (r <- scc) yield {
        // Number the loop's registers in depth-first order from r (children in template order).
        val num = scala.collection.mutable.LinkedHashMap[Int, Int]()
        val todo = scala.collection.mutable.Stack[Int]()
        todo.push(r)
        while (todo.nonEmpty) {
          val v = todo.pop()
          if (!num.contains(v)) {
            num(v) = num.size
            tokens(template(v)).filter(t => members(t) && !num.contains(t)).reverse.foreach(todo.push)
          }
        }
        val sb = new StringBuilder("$loop{")
        for ((v, k) <- num) {
          sb ++= s"$k=" ++= replaceTokens(template(v))(t => if (members(t)) s"@${num(t)}" else "$reg:" + ids(t)) ++= ";"
        }
        r -> sha(sb.append('}').toString)
      }
    }
  }

  /** An enum under one encoding by its complete definition (`ExprText.enumDefinition`), memoized. */
  private val enumMemo = new java.util.IdentityHashMap[SpinalEnum, java.util.IdentityHashMap[SpinalEnumEncoding, String]]()
  def enumKey(senum: SpinalEnum, encoding: SpinalEnumEncoding): String = {
    if (senum == null || encoding == null) return ExprText.enumDefinition(senum, encoding)
    var byEncoding = enumMemo.get(senum)
    if (byEncoding == null) { byEncoding = new java.util.IdentityHashMap(); enumMemo.put(senum, byEncoding) }
    var k = byEncoding.get(encoding)
    if (k == null) { k = ExprText.enumDefinition(senum, encoding); byEncoding.put(encoding, k) }
    k
  }

  private def typeTag(bt: BaseType): String = {
    if (!LibraryClasses.signal(bt.getClass)) return s"$$incomplete:signal ${bt.getClass.getName}"
    val w = try bt.getBitsWidth catch { case _: Throwable => -1 }
    bt match {
      case e: SpinalEnumCraft[_] => s"enum ${enumKey(e.spinalEnum, e.getEncoding)}[$w]"
      case _: Bool               => "Bool"
      case _: UInt               => s"UInt[$w]"
      case _: SInt               => s"SInt[$w]"
      case _: Bits               => s"Bits[$w]"
      case other                 => s"${other.getClass.getName}[$w]"
    }
  }

  /** The typed key of a node, with the allow-list check: the node must be a Spinal class whose every
    * behavior field (`ExprText.params`) the case that keyed it handles; anything else is written
    * `$incomplete:node <class>{...}`, so a construct this key does not model cannot make two designs
    * look equal. Base types are keyed by name and type (their declaration is compared elsewhere). */
  private def keyOf(e: Expression, from: Component, visiting: java.util.IdentityHashMap[BaseType, java.lang.Boolean]): String =
    if (e.isInstanceOf[BaseType] && !LibraryClasses.signal(e.getClass))
      s"$$incomplete:signal ${e.getClass.getName}"
    else {
      val k = keyOfNode(e, from, visiting)
      if (e.isInstanceOf[BaseType] || ExprText.modelled(e.getClass) && ExprText.operandsVisited(e)) k
      else s"$$incomplete:node ${e.getClass.getName}{$k}"
    }

  private def keyOfNode(e: Expression, from: Component,
                        visiting: java.util.IdentityHashMap[BaseType, java.lang.Boolean]): String = {
    def rec(x: Expression): String = squash(keyOf(x, from, visiting))
    def node(head: String): String = {
      val kids = new StringBuilder
      var first = true
      e.foreachExpression { x => if (!first) kids ++= ","; first = false; kids ++= rec(x) }
      val w = e match { case wp: WidthProvider => try s"[${wp.getWidth}]" catch { case _: Throwable => "" }; case _ => "" }
      s"$head$w(${kids.toString})"
    }
    val cls = e.getClass.getName.stripPrefix("spinal.core.internals.").stripPrefix("spinal.core.")
    // An enum node's complete definition under its encoding: element names in order and the value
    // of each (a cast to another encoding, or a changed custom encoding, is other hardware).
    // Each case writes the fields `ExprText.handled` lists for its class.
    val enumTag = e match {
      case ee: EnumEncoded if !e.isInstanceOf[EnumLiteral[_]] => s"@enum ${enumKey(ee.getDefinition, ee.getEncoding)}"
      case _ => ""
    }
    def nodeP(head: String): String = node(head + enumTag)
    e match {
      case bt: BaseType =>
        // Every port has a stable external identity, even when its name starts `_zz_`.
        // Check direction before expanding any compiler temporary or register token.
        val k = if (bt.isInput || bt.isOutput || bt.isInOut)
          s"${KeyEnc.name(nameOf(bt, from))}:${typeTag(bt)}"
        else soleDriver(bt) match {
          // A temporary's tags and attributes (an `init` or `keep` attribute, `noInit`) are part of it:
          // inlined, it is written `$tagged[<tags>](<driver>)`.
          case Some(d) if !visiting.containsKey(bt) =>
            memo(bt, from) {
              visiting.put(bt, true)
              val k = Option(tagsOf(bt)).map(t => s"$$tagged[$t](${rec(d)})").getOrElse(rec(d))
              visiting.remove(bt)
              k
            }
          case _ if generated(bt) && !bt.isReg && !visiting.containsKey(bt) =>
            memo(bt, from) {
              visiting.put(bt, true)
              val k = s"$$gen:${typeTag(bt)}${tagPart(bt)}{${driversKey(bt, from, visiting)}}"
              visiting.remove(bt)
              k
            }
          // A register cuts every combinational path; its id is computed on its own (see `key`).
          case _ if generated(bt) && bt.isReg => token(bt)
          // A temporary met again while it is being expanded (a combinational loop): cut, so incomplete.
          case _ if generated(bt) => s"$$incomplete:${typeTag(bt)}"
          case _                  => s"${KeyEnc.name(nameOf(bt, from))}:${typeTag(bt)}"
        }
        k
      case b: BoolLiteral    => s"lit:Bool=${b.value}"
      case l: EnumLiteral[_] =>
        s"lit:enum ${enumKey(l.senum.spinalEnum, l.getEncoding)}.${KeyEnc.name(l.senum.getName())}#${l.senum.position}"
      // Value, don't-care bits and width in full: a partly poisoned literal (`1x0x`) is not `DontCare`.
      // `hasSpecifiedBitCount` only steers width inference, which is over: the final width is keyed.
      case l: BitVectorLiteral =>
        s"lit:$cls[${l.bitCount}]=${KeyEnc.integerHex(l.value)}" +
          (if (KeyEnc.scalar(l.poisonMask).isEmpty || l.hasPoison()) s"/x${KeyEnc.integerHex(l.poisonMask)}" else "")
      case r: Resize                                   => nodeP(s"$cls<${r.size}>")
      case s: Operator.BitVector.ShiftRightByInt       => nodeP(s"$cls<${s.shift}>")
      case s: Operator.BitVector.ShiftLeftByInt        => nodeP(s"$cls<${s.shift}>")
      case s: Operator.BitVector.ShiftRightByIntFixedWidth => nodeP(s"$cls<${s.shift}>")
      case s: Operator.BitVector.ShiftLeftByIntFixedWidth  => nodeP(s"$cls<${s.shift}>")
      case a: BitVectorBitAccessFixed                  => nodeP(s"$cls<${a.bitId}>")
      case a: BitVectorRangedAccessFixed               => nodeP(s"$cls<${a.hi}:${a.lo}>")
      case a: BitVectorRangedAccessFloating            => nodeP(s"$cls<${a.size}>")
      case r: Operator.Bits.Repeat                     => nodeP(s"$cls<${r.count}>")
      case r: Operator.Bool.Repeat                     => nodeP(s"$cls<${r.count}>")
      case r: Operator.UInt.Repeat                     => nodeP(s"$cls<${r.count}>")
      case r: Operator.SInt.Repeat                     => nodeP(s"$cls<${r.count}>")
      case p: Operator.Formal.PastBits                 => nodeP(s"$cls<${p.delay}>")
      case p: Operator.Formal.PastBool                 => nodeP(s"$cls<${p.delay}>")
      case p: Operator.Formal.PastUInt                 => nodeP(s"$cls<${p.delay}>")
      case p: Operator.Formal.PastSInt                 => nodeP(s"$cls<${p.delay}>")
      case p: Operator.Formal.PastEnum                 => nodeP(s"$cls<${p.delay}>")
      // The random kind by its stable label (its `toString` is an identity hash).
      case r: Operator.Formal.RandomExp                => nodeP(s"$cls<${KeyEnc.label(r.kind)}>")
      // Memory read ports as expressions: every behavior setting of the port (`ExprText.MemPortFields`).
      case r: MemReadAsync      => node(s"$cls<${KeyEnc.name(memName(r.mem, from))},${ExprText.rw(r.readUnderWrite)},vital=${r.isVital}>")
      case r: MemReadSync       => node(s"$cls<${KeyEnc.name(memName(r.mem, from))},${ExprText.rw(r.readUnderWrite)},vital=${r.isVital}," +
                                        s"${cdRawOf(r.clockDomain)}>")
      case r: MemReadWrite      => node(s"$cls<${KeyEnc.name(memName(r.mem, from))},${ExprText.rw(r.readUnderWrite)},${ExprText.dw(r.duringWrite)}," +
                                        s"vital=${r.isVital},${cdRawOf(r.clockDomain)}>")
      case r: MemReadAsyncWrite => node(s"$cls<${KeyEnc.name(memName(r.mem, from))},${ExprText.rw(r.readUnderWrite)},${ExprText.dw(r.duringWrite)}," +
                                        s"vital=${r.isVital},${cdRawOf(r.clockDomain)}>")
      case _                    => nodeP(cls)
    }
  }

  /** The assignments of a temporary, in statement order: `cond && cond: [range] := source` each. */
  private def driversKey(bt: BaseType, from: Component, visiting: java.util.IdentityHashMap[BaseType, java.lang.Boolean]): String = {
    def rec(x: Expression): String = squash(keyOf(x, from, visiting))
    val root = bt.rootScopeStatement
    val parts = Seq.newBuilder[String]
    bt.foreachStatements { st =>
      val conds = List.newBuilder[String]
      var scope = st.parentScope
      while (scope != null && !(scope eq root) && scope.parentStatement != null) {
        scope.parentStatement match {
          case w: WhenStatement =>
            conds += s"${ExprText.whenIdentity(w)}${if (scope eq w.whenTrue) "when" else "else"}:${rec(w.cond)}"
          case sw: SwitchStatement =>
            val el = sw.elements.find(_.scopeStatement eq scope)
            conds += (el match {
              case Some(e) => s"case:${rec(sw.value)}${ExprText.switchBranchKey(sw, e, rec)}"
              case None    => s"default:${rec(sw.value)}${ExprText.switchBranchKey(sw, null, rec)}"
            }) + ExprText.switchFlags(sw)
          case other => conds += s"$$incomplete:scope ${other.getClass.getName}"
        }
        scope = scope.parentStatement.parentScope
      }
      val body = st match {
        case a: AssignmentStatement =>
          val range = a.target match {
            case t: BitAssignmentFixed       => s"(${t.bitId})"
            case t: RangedAssignmentFixed    => s"(${t.hi}:${t.lo})"
            case t: BitAssignmentFloating    => s"(${rec(t.bitId)})"
            case t: RangedAssignmentFloating => s"(${rec(t.offset)},${t.bitCount})"
            case _: BaseType                 => ""
            case t                           => s"($$incomplete:target ${t.getClass.getName})"
          }
          s"${ExprText.assignmentKind(a)}${ExprText.targetIdentity(a.target)}$range:=${rec(a.source)}"
        case other => s"$$incomplete:statement ${other.getClass.getName}"
      }
      parts += (conds.result().reverse :+ body).mkString(" && ")
    }
    parts.result().mkString("; ")
  }

  private def memName(m: Mem[_], from: Component): String = {
    val p = spinalwaves.HglNaming.instancePath(m.component)
    val f = spinalwaves.HglNaming.instancePath(from)
    if (p.startsWith(f)) (p.drop(f.length) :+ m.getName()).mkString(".") else (p :+ m.getName()).mkString(".")
  }
}

object ExprText {
  /** Fields of Spinal's node and statement classes that are not behavior: naming, scope links, phase
    * bookkeeping, source traces, width inference state (the inferred width is keyed), tags (compared
    * where a tag can matter: signals, memories, ports). Audited against SpinalHDL 1.15.0. */
  val InfraFields: Set[String] = Set("scalaTrace", "globalData", "algoInt", "algoIncremental", "inferredWidth",
    "widthWhenNotInferred", "parentScope", "instanceCounter", "spinal$core$Nameable$$mode", "refOwner", "nameableRef",
    "namePriority", "name", "lastScopeStatement", "nextScopeStatement", "dlcLast", "dlcHead", "dlceNext", "dlceLast",
    "compositeAssign", "MuxBuilderEnum$module", "elaborationReadBits", "parent", "_spinalTags", "locationString")

  /** The behavior fields of a class: every instance field (its own and inherited) that is not
    * infrastructure and not an operand (an `Expression`, or a multiplexer's `inputs`). */
  private val paramMemo = new java.util.concurrent.ConcurrentHashMap[Class[_], Set[String]]()
  def params(c: Class[_]): Set[String] = paramMemo.computeIfAbsent(c, { c =>
    val out = Set.newBuilder[String]
    var k: Class[_] = c
    while (k != null && k != classOf[Object]) {
      for (f <- k.getDeclaredFields if !java.lang.reflect.Modifier.isStatic(f.getModifiers)) {
        val operand = classOf[Expression].isAssignableFrom(f.getType) ||
          (f.getName == "inputs" && classOf[scala.collection.Iterable[_]].isAssignableFrom(f.getType))
        if (!operand && !InfraFields(f.getName)) out += f.getName
      }
      k = k.getSuperclass
    }
    out.result()
  })

  /** Allow-list rule: a node is fully keyed when it is one of Spinal's own classes (a subclass from
    * elsewhere may emit other hardware) and every behavior field it has is one its key writes. */
  def modelled(c: Class[_]): Boolean = LibraryClasses.isSpinal(c) && params(c).subsetOf(handled(c))

  /** The `Expression`-typed fields of a class, readable: what `operandsVisited` checks. */
  private val operandMemo = new java.util.concurrent.ConcurrentHashMap[Class[_], Seq[java.lang.reflect.Field]]()
  private def operandFields(c: Class[_]): Seq[java.lang.reflect.Field] = operandMemo.computeIfAbsent(c, { c =>
    val out = Seq.newBuilder[java.lang.reflect.Field]
    var k: Class[_] = c
    while (k != null && k != classOf[Object]) {
      for (f <- k.getDeclaredFields if !java.lang.reflect.Modifier.isStatic(f.getModifiers) &&
        classOf[Expression].isAssignableFrom(f.getType) && !InfraFields(f.getName)) {
        f.setAccessible(true); out += f
      }
      k = k.getSuperclass
    }
    out.result()
  })

  /** Every operand a node holds is one its key walks (`foreachExpression`): an `Expression` field the
    * walk skips (`SuffixExpression.target`) is not in the key, so the node is not modelled. */
  def operandsVisited(e: Expression): Boolean = {
    val fs = operandFields(e.getClass)
    fs.isEmpty || {
      val seen = java.util.Collections.newSetFromMap(new java.util.IdentityHashMap[Expression, java.lang.Boolean]())
      e.foreachExpression(x => seen.add(x))
      fs.forall { f => val v = f.get(e); v == null || seen.contains(v.asInstanceOf[Expression]) }
    }
  }

  /** The parameter fields the keys write for a node of class `c` (one entry per case of
    * `ExprText.keyOfNode`; assignment targets and switch keys are keyed where they are used). */
  def handled(c: Class[_]): Set[String] = {
    def is(k: Class[_]) = k.isAssignableFrom(c)
    import Operator.{BitVector => BV, Formal => F}
    val own: Set[String] =
      if (is(classOf[BoolLiteral])) Set("value")
      else if (is(classOf[EnumLiteral[_]])) Set("senum", "encodingChoice", "encoding")
      else if (is(classOf[BitVectorLiteral])) Set("value", "poisonMask", "bitCount", "hasSpecifiedBitCount")
      else if (is(classOf[Resize])) Set("size")
      else if (Seq(classOf[BV.ShiftRightByInt], classOf[BV.ShiftLeftByInt], classOf[BV.ShiftRightByIntFixedWidth],
        classOf[BV.ShiftLeftByIntFixedWidth]).exists(is)) Set("shift")
      else if (is(classOf[BitVectorBitAccessFixed])) Set("bitId")
      else if (is(classOf[BitVectorRangedAccessFixed])) Set("hi", "lo")
      else if (is(classOf[BitVectorRangedAccessFloating])) Set("size")
      else if (Seq(classOf[Operator.Bits.Repeat], classOf[Operator.Bool.Repeat], classOf[Operator.UInt.Repeat],
        classOf[Operator.SInt.Repeat]).exists(is)) Set("count")
      else if (Seq(classOf[F.PastBits], classOf[F.PastBool], classOf[F.PastUInt], classOf[F.PastSInt], classOf[F.PastEnum])
        .exists(is)) Set("delay")
      else if (is(classOf[F.RandomExp])) Set("kind", "width")
      else if (is(classOf[BitAssignmentFixed])) Set("out", "bitId")
      else if (is(classOf[RangedAssignmentFixed])) Set("out", "hi", "lo")
      else if (is(classOf[BitAssignmentFloating])) Set("out")
      else if (is(classOf[RangedAssignmentFloating])) Set("out", "bitCount")
      else if (is(classOf[SwitchStatementKeyBool])) Set("key")
      else MemPortFields(c)
    // The enum definition field is `enumDef`, `spinalEnum` or (EnumPoison) `senum`: all are `getDefinition`.
    own ++ (if (is(classOf[EnumEncoded]) && !is(classOf[EnumLiteral[_]])) Set("enumDef", "spinalEnum", "senum", "encodingChoice", "encoding")
            else Set.empty)
  }

  /** Behavior fields of the memory port classes, each written into the port's key. */
  val MemPortFields: Class[_] => Set[String] = {
    case c if c == classOf[MemReadAsync]      => Set("width", "readUnderWrite", "isVital", "mem")
    case c if c == classOf[MemReadSync]       => Set("width", "readUnderWrite", "isVital", "mem", "clockDomain")
    case c if c == classOf[MemReadWrite]      => Set("width", "readUnderWrite", "duringWrite", "isVital", "mem", "clockDomain")
    case c if c == classOf[MemReadAsyncWrite] => Set("width", "readUnderWrite", "duringWrite", "isVital", "mem", "clockDomain")
    case c if c == classOf[MemWrite]          => Set("width", "isVital", "mem", "clockDomain")
    case _                                    => Set.empty
  }
  def rw(p: ReadUnderWritePolicy): String = if (p == null) "rw=null"
    else if (LibraryClasses.isSpinal(p.getClass)) s"rw=${p.readUnderWriteString}" else "$incomplete:read-under-write policy"
  def dw(p: DuringWritePolicy): String = if (p == null) "dw=null"
    else if (LibraryClasses.isSpinal(p.getClass)) s"dw=${p.duringWriteString}" else "$incomplete:during-write policy"

  private def checkedMasked(ml: MaskedLiteral): Option[MaskedLiteral] = Option(ml).filter(m =>
    LibraryClasses.exact(m.getClass, classOf[MaskedLiteral]) && m.value != null && m.careAbout != null &&
      KeyEnc.scalar(m.value).isDefined && KeyEnc.scalar(m.careAbout).isDefined)

  def maskedText(ml: MaskedLiteral): Option[String] = checkedMasked(ml).map(m =>
    "M\"" + (0 until m.width).reverse.map(b =>
      if (!m.careAbout.testBit(b)) '-' else if (m.value.testBit(b)) '1' else '0').mkString + "\"")

  def plainLiteral(l: BitVectorLiteral): Option[BigInt] =
    Option(l).filter(v => modelled(v.getClass) && v.value != null && KeyEnc.scalar(v.value).isDefined &&
      KeyEnc.scalar(v.poisonMask).isDefined && !v.hasPoison()).map(_.value)

  /** Typed form of a `switch` case key: a masked literal as `M"01-"`, any other key by `keyOf`. */
  def caseKey(k: Expression, keyOf: Expression => String): String = k match {
    case kb: SwitchStatementKeyBool if !modelled(kb.getClass) => s"$$incomplete:case key ${kb.getClass.getName}"
    case kb: SwitchStatementKeyBool if kb.key != null =>
      if (!LibraryClasses.exact(kb.getClass, classOf[SwitchStatementKeyBool])) "$incomplete:masked literal"
      else maskedText(kb.key).getOrElse("$incomplete:masked literal")
    case kb: SwitchStatementKeyBool => keyOf(kb.cond)
    case other                      => keyOf(other)
  }

  /** The value a case key matches when it matches exactly one value (a literal without don't-care
    * bits, a fully specified masked literal), reduced to the switch value's width; None otherwise. */
  private def exactValue(k: Expression, width: Option[Int]): Option[BigInt] = if (!modelled(k.getClass)) None else k match {
    case kb: SwitchStatementKeyBool if kb.key != null =>
      checkedMasked(kb.key).filter(m => (0 until m.width).forall(m.careAbout.testBit)).map(_.value)
    case kb: SwitchStatementKeyBool => None
    case b: BoolLiteral             => Some(if (b.value) BigInt(1) else BigInt(0))
    case e: EnumLiteral[_]          => try Option(e.getValue()).filter(v => KeyEnc.scalar(v).isDefined)
      catch { case scala.util.control.NonFatal(_) => None }
    case l: BitVectorLiteral => plainLiteral(l).flatMap(v => width.map(w => v.mod(BigInt(1) << w)))
    case _                          => None
  }

  /** True when no two case keys of `sw` can match the same value: every key matches exactly one value
    * and all those values differ. Then a case's condition does not depend on the cases before it. */
  def exclusiveCases(sw: SwitchStatement): Boolean = {
    val width = sw.value match {
      case wp: WidthProvider => try Some(wp.getWidth) catch { case scala.util.control.NonFatal(_) => None }
      case _                 => None
    }
    val values = sw.elements.toSeq.flatMap(_.keys).map(exactValue(_, width))
    values.forall(_.isDefined) && values.flatten.distinct.size == values.size
  }

  /** The keys of a list of case elements, in order: keys of one element joined by `|`, elements by `;`
    * (an element with an empty body counts like any other). */
  private def elementsKey(els: Seq[SwitchStatementElement], keyOf: Expression => String): String =
    els.map(_.keys.map(caseKey(_, keyOf)).mkString("|")).mkString(";")

  /** What selects one branch of a `switch`, after the value's key. A case (`el`) is its own keys, and,
    * when keys may overlap (`exclusiveCases` false), `|not{...}` with every earlier case's keys: the
    * first matching case wins, so an earlier key, even of a case with an empty body, blocks it. The
    * default (`el` null) is `|not{...}` with every case's keys in order, empty cases included. */
  def switchBranchKey(sw: SwitchStatement, el: SwitchStatementElement, keyOf: Expression => String): String =
    if (el == null) s"|not{${elementsKey(sw.elements.toSeq, keyOf)}}"
    else {
      val own = "|" + el.keys.map(caseKey(_, keyOf)).mkString("|")
      val before = sw.elements.toSeq.takeWhile(_ ne el)
      if (before.isEmpty || exclusiveCases(sw)) own else own + s"|not{${elementsKey(before, keyOf)}}"
    }

  /** The case keys whose signals a branch's condition reads: its own, the earlier ones when they can
    * block it, and every case key for the default. */
  def switchBranchReads(sw: SwitchStatement, el: SwitchStatementElement): Seq[Expression] =
    if (el == null) sw.elements.toSeq.flatMap(_.keys)
    else if (exclusiveCases(sw)) el.keys.toSeq
    else sw.elements.toSeq.takeWhile(_ ne el).flatMap(_.keys) ++ el.keys

  /** A `switch`'s generation flags, when not the default (so existing keys keep their form). */
  def switchFlags(sw: SwitchStatement): String =
    (if (!LibraryClasses.exact(sw.getClass, classOf[SwitchStatement]) ||
      !sw.elements.forall(el => LibraryClasses.exact(el.getClass, classOf[SwitchStatementElement]))) "$incomplete:switch " else "") +
    (if (sw.coverUnreachable) "|coverUnreachable" else "") + (if (sw.removeDuplication) "|removeDuplication" else "")

  def whenIdentity(w: WhenStatement): String =
    if (LibraryClasses.exact(w.getClass, classOf[WhenStatement])) "" else s"$$incomplete:when ${w.getClass.getName} "

  def targetIdentity(t: Expression): String = {
    val known = t match {
      case bt: BaseType => LibraryClasses.signal(bt.getClass)
      case _ => modelled(t.getClass)
    }
    if (known) "" else s"$$incomplete:target ${t.getClass.getName} "
  }

  /** `data`, `init` (reset value) or `initial` (power-on value); any other assignment class is not modelled. */
  def assignmentKind(a: AssignmentStatement): String = a.getClass match {
    case c if LibraryClasses.exact(c, classOf[DataAssignmentStatement])    => "data"
    case c if LibraryClasses.exact(c, classOf[InitAssignmentStatement])    => "init"
    case c if LibraryClasses.exact(c, classOf[InitialAssignmentStatement]) => "initial"
    case c                                             => s"$$incomplete:statement ${c.getName} "
  }

  /** An enum's complete definition under `encoding`: its name, the encoding's name, native flag and
    * width, and every element in declaration order with the value the encoding gives it
    * (`State@custom[2]{a=1,b=2,c=0}`), so reordered elements or a changed custom encoding differ.
    * When a value cannot be evaluated (an encoding that throws, no definition or encoding) the key
    * is `$incomplete:enum`. */
  def enumDefinition(senum: SpinalEnum, encoding: SpinalEnumEncoding): String = {
    if (senum == null || encoding == null)
      return s"$$incomplete:enum ${Option(senum).map(_.getName("enum")).orNull}@${Option(encoding).map(_.getName()).orNull}"
    if (!LibraryClasses.isSpinal(encoding.getClass) ||
      !senum.elements.forall(el => LibraryClasses.exact(el.getClass, classOf[SpinalEnumElement[_]])))
      return "$incomplete:enum identity"
    val name = KeyEnc.name(senum.getName("enum"))
    try {
      val elements = senum.elements.map(el => s"${KeyEnc.name(el.getName())}=${KeyEnc.integerHex(encoding.getValue(el))}").mkString(",")
      s"$name@${KeyEnc.name(encoding.getName())}${if (encoding.isNative) "/native" else ""}[${encoding.getWidth(senum)}]{$elements}"
    } catch {
      case t: Throwable if scala.util.control.NonFatal(t) || t.isInstanceOf[NotImplementedError] =>
        s"$$incomplete:enum $name@${encoding.getName()} (${t.getClass.getSimpleName})"
    }
  }

  /** Register loops larger than this get an `$incomplete:` id (the canonical numbering costs the
    * square of the loop size). BOOM small's largest loop of generated registers has 31. */
  val LoopLimit = 2000

  /** True when a typed key (or a part of one) is not complete: see `ExprText.key`. */
  def isIncomplete(k: String): Boolean = k != null && (k.contains("$incomplete:") || k.contains("h!:"))
}
