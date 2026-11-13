package spinaldb

import java.io.File
import java.nio.file.{Files, Paths}
import java.sql.DriverManager

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

import scala.collection.mutable.ArrayBuffer

/** Registers declared inside a `for` loop (as spinal-boom's ROB does): the Vec has no name. */
class LoopVecs extends Component {
  val io = new Bundle { val sel = in UInt (2 bits); val o = out Vec (Bool(), 2) }
  for (w <- 0 until 2) {
    val v = Vec.fill(4)(RegInit(False))
    v(io.sel) := !v(io.sel)
    io.o(w) := v(io.sel)
  }
}

/** Review probes (/tmp/review-design-sol/ReviewDbProbe.scala): changes the display text cannot show. */
class CastDesign(signed: Boolean) extends Component {
  setDefinitionName("CastDesign")
  val io = new Bundle { val a = in UInt (8 bits); val y = out UInt (8 bits) }
  io.y := (if (signed) (io.a.asSInt >> 3).resize(8).asUInt else (io.a >> 3).resize(8))
}
class RomDesign(value: Int) extends Component {
  setDefinitionName("RomDesign")
  val io = new Bundle { val a = in UInt (2 bits); val y = out Bits (8 bits) }
  val rom = Mem(Bits(8 bits), 4)
  rom.initBigInt(Seq.fill(4)(BigInt(value)))
  io.y := rom.readAsync(io.a)
}
class MaskDesign extends Component {
  val io = new Bundle {
    val addr = in UInt (2 bits); val data = in Bits (32 bits); val mask = in Bits (4 bits); val en = in Bool ()
    val y = out Bits (32 bits)
  }
  val mem = Mem(Bits(32 bits), 4)
  mem.write(io.addr, io.data, io.en, mask = io.mask)
  io.y := mem.readAsync(io.addr)
}

/** Round-2 review probes (/tmp/review2-design): a `mux` result is a temporary with one driver per
  * case, so its constants must reach the key of `io_y`; a line shift renames `when_<File>_l<N>`. */
class MuxDesign(k: Int) extends Component {
  setDefinitionName("MuxDesign")
  val io = new Bundle { val sel = in UInt (2 bits); val y = out UInt (8 bits) }
  io.y := io.sel.mux(0 -> U(1, 8 bits), 1 -> U(k, 8 bits), default -> U(0, 8 bits))
}
class ShiftA extends Component {
  setDefinitionName("Shift")
  val io = new Bundle { val a = in UInt (8 bits); val b = in UInt (8 bits); val y = out UInt (8 bits) }
  val r = Reg(UInt(8 bits)) init 0
  when(io.a > io.b) { r := io.a - io.b } otherwise { r := r + 1 }
  io.y := r
}
class ShiftB extends Component {
  setDefinitionName("Shift")
  val io = new Bundle { val a = in UInt (8 bits); val b = in UInt (8 bits); val y = out UInt (8 bits) }

  val r = Reg(UInt(8 bits)) init 0
  when(io.a > io.b) { r := io.a - io.b } otherwise { r := r + 1 }
  io.y := r
}
class ShiftC extends Component { // ShiftB with a real change in the condition
  setDefinitionName("Shift")
  val io = new Bundle { val a = in UInt (8 bits); val b = in UInt (8 bits); val y = out UInt (8 bits) }
  val r = Reg(UInt(8 bits)) init 0
  when(io.a >= io.b) { r := io.a - io.b } otherwise { r := r + 1 }
  io.y := r
}

/** Round-4 review probes (/tmp/review4-design): `RegNext(...) init k` is a generated register, so
  * its reset value must reach the diff; a register and a memory write port under the same clock
  * signal but another edge, reset kind or reset polarity must not diff as identical. */
class GenRegDesign(k: Int) extends Component {
  setDefinitionName("GenRegDesign")
  val io = new Bundle { val a = in UInt (8 bits); val y = out UInt (8 bits) }
  io.y := (RegNext(io.a + U(1, 8 bits)) init k)
}
class DomainDesign(variant: String) extends Component {
  setDefinitionName("DomainDesign")
  val io = new Bundle {
    val a = in UInt (8 bits); val addr = in UInt (2 bits); val y = out UInt (8 bits); val z = out UInt (8 bits)
  }
  val base = ClockDomain.current
  val cd = variant match {
    case "fall" => base.copy(config = base.config.copy(clockEdge = FALLING))
    case "sync" => base.copy(config = base.config.copy(resetKind = SYNC))
    case "low"  => base.copy(config = base.config.copy(resetActiveLevel = LOW))
    case _      => base
  }
  val area = new ClockingArea(cd) {
    val r = Reg(UInt(8 bits)) init 0
    r := io.a
    val mem = Mem(UInt(8 bits), 4)
    mem.write(io.addr, io.a)
  }
  io.y := area.r
  io.z := area.mem.readAsync(io.addr)
}

/** Round-5 review probes (/tmp/review5-b): a clock enable or soft reset whose polarity flips, and
  * two unnamed `RegNext` operands that swap sides (`a - b` vs `b - a`), must not diff as identical. */
class PolarityDesign(soft: Boolean, low: Boolean) extends Component {
  setDefinitionName("PolarityDesign")
  val io = new Bundle { val a = in UInt (8 bits); val en = in Bool (); val y = out UInt (8 bits) }
  val base = ClockDomain.current
  val active: Polarity = if (low) LOW else HIGH
  val cd = if (soft) base.copy(softReset = io.en, config = base.config.copy(softResetActiveLevel = active))
           else base.copy(clockEnable = io.en, config = base.config.copy(clockEnableActiveLevel = active))
  val area = new ClockingArea(cd) { val r = Reg(UInt(8 bits)) init 0; r := io.a }
  io.y := area.r
}
class SwapDesign(flip: Boolean) extends Component {
  setDefinitionName("SwapDesign")
  val io = new Bundle { val a = in UInt (8 bits); val b = in UInt (8 bits); val y = out UInt (8 bits) }
  def calc(): UInt = {
    val a = RegNext(io.a + 1) init 1
    val b = RegNext(io.b + 1) init 2
    if (flip) b - a else a - b
  }
  io.y := calc()
}

/** Round-6 review probes (/tmp/review6/DeepProbe.scala): the swap of two `stages`-deep `RegNext`
  * chains must differ at any depth (the /4 key stopped four registers deep); `LoopDesign` has
  * generated registers in a loop, `dense` with every register reading every other one. */
class DeepSwapDesign(flip: Boolean, stages: Int) extends Component {
  setDefinitionName("DeepSwap")
  val io = new Bundle { val a = in UInt (8 bits); val b = in UInt (8 bits); val y = out UInt (8 bits) }
  def calc(): UInt = {
    def pipe(x: UInt): UInt = (0 until stages).foldLeft(x)((v, _) => RegNext(v) init 0)
    val a = pipe(io.a + 1)
    val b = pipe(io.b + 1)
    if (flip) b - a else a - b
  }
  io.y := calc()
}
class LoopDesign(flip: Boolean, n: Int, dense: Boolean = false) extends Component {
  setDefinitionName("LoopDesign")
  val io = new Bundle { val a = in UInt (8 bits); val b = in UInt (8 bits); val y = out UInt (8 bits) }
  def calc(): UInt = {
    val r = Seq.fill(n)(Reg(UInt (8 bits)) init 0)
    for (i <- 0 until n) {
      val next = r((i + 1) % n)
      val sum = r.reduce(_ + _)
      r(i) := (if (i == 0) (if (dense) (if (flip) next - sum else sum - next) else if (flip) io.b - next else next - io.b)
               else if (dense) sum - next else next + io.a)
    }
    r(0)
  }
  io.y := calc()
}

/** Round-7 review probes (/tmp/review7/ReviewProbe.scala): a generated clock enable whose logic
  * changes (`io.a > 1` vs `> 2`), and two distinct generated registers with equal drivers read in
  * different places (`(r - r) - s` vs `(r - s) - s`), must not diff as identical. */
class EnableLogicDesign(k: Int) extends Component {
  setDefinitionName("EnableLogic")
  val io = new Bundle { val a = in UInt (8 bits); val d = in UInt (8 bits); val y = out UInt (8 bits) }
  val area = new ClockingArea(ClockDomain.current.copy(clockEnable = io.a > k)) {
    val r = RegNext(io.d) init 0
    io.y := r
  }
}
class SharingDesign(mode: Int) extends Component {
  setDefinitionName("Sharing")
  val io = new Bundle { val a = in UInt (8 bits); val y = out UInt (8 bits); val z = out UInt (8 bits) }
  def calc(): Unit = {
    val r = RegNext(io.a + 1)
    val s = RegNext(io.a + 1)
    io.y := (if (mode == 0) (r - r) - s else (r - s) - s)
    io.z := s
  }
  calc()
}

// No-argument forms for spinaldb.Main (rvw/tests/data/regen.sh builds the Python fixtures from them).
class CastUnsigned extends CastDesign(false)
class CastSigned extends CastDesign(true)
class Rom1 extends RomDesign(1)
class Rom2 extends RomDesign(2)
class Mux2 extends MuxDesign(2)
class Mux3 extends MuxDesign(3)
class GenInit1 extends GenRegDesign(1)
class GenInit2 extends GenRegDesign(2)
class DomainRise extends DomainDesign("rise")
class DomainFall extends DomainDesign("fall")
class DomainSync extends DomainDesign("sync")
class DomainLow extends DomainDesign("low")
class EnableHigh extends PolarityDesign(false, false)
class EnableLow extends PolarityDesign(false, true)
class SoftHigh extends PolarityDesign(true, false)
class SoftLow extends PolarityDesign(true, true)
class SwapA extends SwapDesign(false)
class SwapB extends SwapDesign(true)
class DeepA extends DeepSwapDesign(false, 5)
class DeepB extends DeepSwapDesign(true, 5)
class EnableLogic1 extends EnableLogicDesign(1)
class EnableLogic2 extends EnableLogicDesign(2)
class Sharing0 extends SharingDesign(0)
class Sharing1 extends SharingDesign(1)
class Rw0 extends RwDesign(0)
class Rw1 extends RwDesign(1)
class Box1 extends BoxDesign(1)
class Box2 extends BoxDesign(2)
class PlainNot extends UnsupportedDesign(0)
class SaltedNot1 extends UnsupportedDesign(1)
class SaltedNot2 extends UnsupportedDesign(2)
class InitReg extends InitialDesign(false)
class InitialReg extends InitialDesign(true)

// Round 8 (/tmp/review8/NewProbe.scala): a read/write port's read-under-write policy, and a
// BlackBox generic, were not part of the keys: both diffs said `identical: true`.
class RwDesign(mode: Int) extends Component {
  setDefinitionName("Rw")
  val io = new Bundle { val a = in UInt(2 bits); val d = in Bits(8 bits); val en, wr = in Bool(); val y = out Bits(8 bits) }
  val mem = Mem(Bits(8 bits), 4)
  mem.initBigInt(Seq(1, 2, 3, 4).map(BigInt(_)))
  // Modes the Verilog backend can emit: readFirst / writeFirst with doRead; dontCare with dontRead / doRead.
  io.y := mem.readWriteSync(io.a, io.d, io.en, io.wr, readUnderWrite = Seq(readFirst, writeFirst, dontCare, dontCare)(mode),
    duringWrite = if (mode == 2) dontRead else doRead)
}
class ExternalBb(k: Int, rtl: String = null) extends BlackBox {
  setDefinitionName("External")
  addGeneric("K", k)
  val io = new Bundle { val a = in Bits(8 bits); val y = out Bits(8 bits) }
  noIoPrefix()
  if (rtl != null) addRTLPath(rtl)
}
class BoxDesign(k: Int, rtl: String = null) extends Component {
  setDefinitionName("Box")
  val io = new Bundle { val a = in Bits(8 bits); val y = out Bits(8 bits) }
  val b = new ExternalBb(k, rtl)
  b.io.a := io.a
  io.y := b.io.y
}
/** `salt` > 0 uses a node class the key builder does not model. */
class UnsupportedDesign(salt: Int) extends Component {
  val io = new Bundle { val a = in Bits(8 bits); val y = out Bits(8 bits) }
  io.y := (if (salt > 0) SpinalDBTestHooks.saltedNot(io.a, salt) else ~io.a)
}
class InitialDesign(initial: Boolean) extends Component {
  val io = new Bundle { val a = in UInt(8 bits); val y = out UInt(8 bits) }
  val r = Reg(UInt(8 bits))
  if (initial) r.initial(5) else r.init(5)
  r := io.a
  io.y := r
}
/** `1x0x` vs `0x1x`: literals with don't-care bits used to key as `DontCare` whatever their value. */
class PoisonDesign(v: Int) extends Component {
  val io = new Bundle { val y = out Bits(4 bits) }
  SpinalDBTestHooks.assignPoisoned(io.y, if (v == 0) 8 else 2, 5)
}
/** `t` in binary or Gray code: same width, other hardware. */
class EnumCastDesign(gray: Boolean) extends Component {
  object E extends SpinalEnum { val A, B, C = newElement() }
  val io = new Bundle { val s = in(E()); val y = out Bits(2 bits) }
  val t = E(if (gray) spinal.core.graySequential else spinal.core.binarySequential)
  t := io.s
  io.y := t.asBits.resized
}

// Round 9 (/tmp/review9/Adversarial.scala): enum keys named the encoding only, so reordered elements
// and a changed custom encoding diffed as identical; a BlackBox body's `include`d header was not hashed.
class EnumOrderDesign(mode: Int, reorder: Boolean) extends Component {
  setDefinitionName("Enc")
  val e = new SpinalEnum(binarySequential)
  e.setName("State")
  val names = if (reorder && mode == 1) Seq("b", "a", "c") else Seq("a", "b", "c")
  val values = names.map(n => n -> e.newElement(n)).toMap
  if (!reorder) e.defaultEncoding = SpinalEnumEncoding("custom", i => BigInt(if (mode == 0) i else (i + 1) % 3))
  val io = new Bundle { val sel = in Bool(); val y = out Bits(2 bits) }
  val state = e()
  state := values("a")
  when(io.sel) { state := values("b") }
  io.y := state.asBits
}
class EnumCustom0 extends EnumOrderDesign(0, false)
class EnumCustom1 extends EnumOrderDesign(1, false)
class EnumOrder0 extends EnumOrderDesign(0, true)
class EnumOrder1 extends EnumOrderDesign(1, true)
class IncludeBb(path: String, k: Int = 1) extends BlackBox {
  setDefinitionName("External")
  if (k != 1) addGeneric("K", k)
  addRTLPath(path)
  val io = new Bundle { val a = in Bits(8 bits); val y = out Bits(8 bits) }
  noIoPrefix()
}
class IncludeTop(path: String, k: Int = 1) extends Component {
  setDefinitionName("ExtTop")
  val io = new Bundle { val a = in Bits(8 bits); val y = out Bits(8 bits) }
  val b = new IncludeBb(path, k)
  b.io.a := io.a
  io.y := b.io.y
}

/** Round 9 audit: tag payloads. `ClockDomainReportTag` prints its clock domain as the clock's name. */
case class CaseTag(k: Int) extends SpinalTag
class HiddenTag(val k: Int) extends SpinalTag { override def toString = "HiddenTag" }
class TagDesign(mode: String, file: String = null) extends Component {
  setDefinitionName("Tagged")
  val io = new Bundle { val a = in Bool(); val y = out Bool() }
  io.y := io.a
  val cd = ClockDomain.external("cd", config = ClockDomainConfig(resetActiveLevel = if (mode == "low") LOW else HIGH))
  mode match {
    case "high" | "low" => io.y.addTag(ClockDomainReportTag(cd))
    case "case1"        => io.y.addTag(CaseTag(1))
    case "case2"        => io.y.addTag(CaseTag(2))
    case "hidden"       => io.y.addTag(new HiddenTag(1))
    case "file"         => io.y.addAttribute("ram_init_file", file)
    case "symbols1"     => io.y.addTag(MemSymbolesTag(Seq(MemSymbolesMapping("s0", 0 until 4), MemSymbolesMapping("s1", 4 until 8))))
    case "symbols2"     => io.y.addTag(MemSymbolesTag(Seq(MemSymbolesMapping("s0", 0 until 2), MemSymbolesMapping("s1", 2 until 8))))
  }
}

// Round 10 (/tmp/review10-a/DefaultPriority.scala, TagClockExpr.scala): a `switch` default's key
// omitted the case keys (an empty `is(mode)` decides when the default applies), and a generated
// register read only as a clock enable lost its attributes (`init` is a power-on value in Yosys).
class DefaultPriorityDesign(mode: Int, temp: Boolean) extends Component {
  setDefinitionName("PriorityDesign")
  val io = new Bundle { val sel = in Bits(2 bits); val y, z = out Bool() }
  io.z := False
  if (!temp) {
    io.y := False
    switch(io.sel) { is(B(mode, 2 bits)) {}; default { io.y := True } }
  } else { // the same switch driving a compiler temporary (`$gen` key)
    io.y := { val t = Bool(); t := False; switch(io.sel) { is(B(mode, 2 bits)) {}; default { t := True } }; t }
  }
}
class Default0 extends DefaultPriorityDesign(0, false)
class Default1 extends DefaultPriorityDesign(1, false)
class DefaultTemp0 extends DefaultPriorityDesign(0, true)
class DefaultTemp1 extends DefaultPriorityDesign(1, true)
/** Overlapping masked keys: the first matching case wins, so the order of the cases is behavior. */
class OverlapDesign(swap: Boolean) extends Component {
  setDefinitionName("Overlap")
  val io = new Bundle { val sel = in Bits(2 bits); val y, z = out Bool() }
  io.y := False; io.z := False
  switch(io.sel) {
    if (!swap) { is(M"1-") { io.y := True }; is(M"-1") { io.z := True } }
    else { is(M"-1") { io.z := True }; is(M"1-") { io.y := True } }
  }
}
class Overlap0 extends OverlapDesign(false)
class Overlap1 extends OverlapDesign(true)
class TagClockDesign(mode: String) extends Component {
  setDefinitionName("TagClockDesign")
  val io = new Bundle { val en = in Bool(); val y = out UInt(8 bits) }
  val boot = ClockDomain.current.copy(reset = null, config = ClockDomainConfig(resetKind = BOOT))
  def enable(): Bool = { // an unnamed (generated) register
    val en = RegNext(!io.en)
    mode match {
      case "init0"  => en.addAttribute("init", 0)
      case "init1"  => en.addAttribute("init", 1)
      case "hidden" => en.addTag(new HiddenTag(1))
      case _        =>
    }
    en
  }
  val area = new ClockingArea(boot) {
    val inner = new ClockingArea(boot.copy(clockEnable = enable())) { val r = Reg(UInt(8 bits)) init 0; r := r + 1; io.y := r }
  }
}
class TagClock0 extends TagClockDesign("init0")
class TagClock1 extends TagClockDesign("init1")
class TagClockHidden extends TagClockDesign("hidden")
/** Instance and definition attributes of a child component are emitted into the Verilog. */
class AttrChild(mode: Int) extends Component {
  setDefinitionName("AttrChild")
  val io = new Bundle { val a = in Bool(); val y = out Bool() }
  io.y := !io.a
  if (mode == 1) definition.addAttribute("keep_hierarchy", "yes")
}
class CompAttrDesign(mode: Int) extends Component {
  setDefinitionName("CompAttr")
  val io = new Bundle { val a = in Bool(); val y = out Bool() }
  val c = new AttrChild(mode)
  if (mode == 2) c.addAttribute("dont_touch", "true")
  c.io.a := io.a
  io.y := c.io.y
}
class CompAttr0 extends CompAttrDesign(0)
class CompAttr1 extends CompAttrDesign(1)
class CompAttr2 extends CompAttrDesign(2)

// Round 11 (/tmp/review11-a/Named.scala, Extra.scala): registers the user named like Spinal line
// names (`when_Test_l12`) were masked as moved code, port order was not stored, a Scala `object` tag
// was keyed by its class only, and an assertion message `when_Test_l12` was masked.
class NamedRegsDesign(mode: Int) extends Component {
  setDefinitionName("NamedRegs")
  val io = new Bundle { val a, b = in UInt(8 bits); val y, z = out UInt(8 bits) }
  val first = RegNext(io.a) init 0; first.setName("when_Test_l12")
  val second = RegNext(io.b) init 0; second.setName("when_Test_l13")
  val third = UInt(8 bits); third.setName("when_Test_l14") // a user wire with a line-name lookalike
  third := io.a + io.b
  io.y := (if (mode == 0) first - second else second - first)
  io.z := third
}
class PortOrderDesign(mode: Int) extends Component {
  setDefinitionName("Ports")
  val io = new Bundle {
    val xs = if (mode == 0) Seq("a", "b") else Seq("b", "a")
    val pins = xs.map(n => n -> in(Bool()).setName(n)).toMap
    val y = out Bool()
  }
  io.y := io.pins("a") && !io.pins("b")
}
object ObjPayload extends SpinalTag { var value = 0 }
object ObjStateless extends SpinalTag
object ObjOpaque extends SpinalTag { val ref = new Object }
class ObjTagDesign(mode: Int) extends Component {
  setDefinitionName("ObjectTag")
  val io = new Bundle { val a = in Bool(); val y = out Bool() }
  io.y := io.a
  mode match {
    case 0 | 1 => ObjPayload.value = mode; io.y.addTag(ObjPayload)
    case 2     => io.y.addTag(ObjStateless)
    case 3     => io.y.addTag(ObjOpaque)
  }
}
class AssertMsgDesign(mode: Int) extends Component {
  setDefinitionName("Assertion")
  val io = new Bundle { val a = in Bool(); val y = out Bool() }
  io.y := io.a
  assert(io.a, if (mode == 0) "when_Test_l12" else "when_Test_l13")
}
class NamedRegs0 extends NamedRegsDesign(0)
class NamedRegs1 extends NamedRegsDesign(1)
class PortOrder0 extends PortOrderDesign(0)
class PortOrder1 extends PortOrderDesign(1)
class ObjTag0 extends ObjTagDesign(0)
class ObjTag1 extends ObjTagDesign(1)
class AssertMsg0 extends AssertMsgDesign(0)
class AssertMsg1 extends AssertMsgDesign(1)

// Round 12 (/tmp/review12-a/MemAttr.scala, More.scala, More2.scala, MoreFmt.scala): an attribute
// subclass's emitted eligibility and fields were not keyed, a `$`-named object field was dropped,
// strings in tags and assertion messages were written unescaped (so `Vector("a\",\"b")` and
// `Vector("a","b")` had one key), and assertion kind, severity and trigger were keyed by their
// identity `toString` (`AssertStatementKind@1b2c3d`), which changes between runs.
class LangAttribute(val enabled: Boolean) extends AttributeFlag("keep") {
  override def isLanguageReady(l: Language): Boolean = enabled
}
class FieldAttribute(val k: Int) extends AttributeFlag("keep")
class IoAttribute extends AttributeFlag("keep") { override def ioTag = true }
class AssignedAttribute extends AttributeFlag("keep") { override def isAssignedTo(that: SpinalTagReady) = true }
class RefAttribute extends AttributeFlag("keep") { val ref = new Object }
object DollarPayload extends SpinalTag { var `$payload` = 0 }
case class SeqTag(values: Vector[String]) extends SpinalTag
case class AnyTag(v: Any) extends SpinalTag
class Round12Design(kind: String, mode: Int) extends Component {
  setDefinitionName("Round12")
  val io = new Bundle { val a = in Bool(); val y = out Bool() }
  io.y := io.a
  kind match {
    case "plain"     => io.y.addTag(new AttributeFlag("keep"))
    case "lang"      => io.y.addTag(new LangAttribute(mode == 0))
    case "field"     => io.y.addTag(new FieldAttribute(mode))
    case "io"        => io.y.addTag(new IoAttribute)
    case "assigned"  => io.y.addTag(new AssignedAttribute)
    case "ref"       => io.y.addTag(new RefAttribute)
    case "verilator" => io.y.addTag(Verilator.public)
    case "dollar"    => DollarPayload.`$payload` = mode; io.y.addTag(DollarPayload)
    case "seq"       => io.y.addTag(SeqTag(if (mode == 0) Vector("a\",\"b") else Vector("a", "b")))
    case "num"       => io.y.addTag(AnyTag(if (mode == 0) 1 else 1L))
    case "control"   => io.y.addTag(AnyTag(if (mode == 0) "\u00010\u0001" else "\\u00010\\u0001"))
    case "set"       => io.y.addTag(AnyTag(if (mode == 0) Set("x", "y", "z", "w", "v") else Set("v", "w", "z", "y", "x")))
    case "assert"    => assert(io.a, if (mode == 0) Seq[Any]("a\",\"b") else Seq[Any]("a", "b"))
    case "assertSig" => assert(io.a, if (mode == 0) Seq[Any]("hi\",io_a:Bool,\"") else Seq[Any]("hi", io.a, ""))
    case "assertFmt" => assert(io.a, if (mode == 0) Seq[Any]("%\",\"m") else Seq[Any]("%", "m"))
  }
}
/** Every assertion kind, severity and trigger, and a formal random value: what the identity-hash sweep reads. */
class FormalKinds extends Component {
  setDefinitionName("FormalKinds")
  val io = new Bundle { val a = in Bool(); val y = out Bool(); val z = out UInt(4 bits) }
  io.y := io.a
  io.z := spinal.core.formal.anyseq(UInt(4 bits))
  assert(io.a, "note", NOTE); assert(io.a, "warning", WARNING); assert(io.a, "error", ERROR); assert(io.a, "failure", FAILURE)
  assume(io.a); cover(io.a); assumeInitial(io.a)
}
class MemAttrDesign(mode: Int) extends Component {
  setDefinitionName("MemAttr")
  val io = new Bundle { val a = in UInt(2 bits); val d = in Bits(8 bits); val en = in Bool(); val y = out Bits(8 bits) }
  val mem = Mem(Bits(8 bits), 4)
  mem.addTag(new LangAttribute(mode == 0))
  mem.write(io.a, io.d, io.en)
  io.y := mem.readAsync(io.a)
}
class Round12Seq0 extends Round12Design("seq", 0)
class Round12Seq1 extends Round12Design("seq", 1)
class Round12Assert0 extends Round12Design("assertSig", 0)
class Round12Assert1 extends Round12Design("assertSig", 1)
class Round12Lang0 extends Round12Design("lang", 0)
class Round12Lang1 extends Round12Design("lang", 1)

// Round 13 (/tmp/review13-a/Attack.scala): attributes were sorted, so `init` 0 then 1 (the netlist
// takes 1) and 1 then 0 had one key; object fields named `bitmap$0` or `serialVersionUID` were left out
// by name, so a user's field with that name was not compared. Below: what the Scala 2.13 compiler
// really adds (a lazy val's bitmap, `@SerialVersionUID`), and a constant `final val`, which has no field.
object R13Bitmap extends SpinalTag { var `bitmap$0`: Int = 0 }
object R13Serial extends SpinalTag { var serialVersionUID: Long = 0 }
object R13Lazy extends SpinalTag { lazy val v: Int = 3 }
@SerialVersionUID(7L) object R13Annotated extends SpinalTag
object R13Const0 extends SpinalTag { final val k = 0 }
object R13Const1 extends SpinalTag { final val k = 1 }
trait R13UserBitmapTrait { var `bitmap$0`: Int = 0 }
object R13TraitBitmap extends SpinalTag with R13UserBitmapTrait
case class R13CaseBitmap(x: Int) extends SpinalTag { @volatile private var payload: Boolean = false; def touch(): Unit = payload = true }
class R13ConstAttribute extends AttributeFlag("keep") { final val k = 1 }
class Round13Design(kind: String, mode: Int) extends Component {
  setDefinitionName("Round13")
  val io = new Bundle { val a = in Bool(); val y = out Bool() }
  kind match {
    case "order" =>
      val r = RegNext(io.a); r.setName("r"); io.y := r
      if (mode == 0) { r.addAttribute("init", 0); r.addAttribute("init", 1) }
      else { r.addAttribute("init", 1); r.addAttribute("init", 0) }
    case other =>
      io.y := io.a
      other match {
        case "bitmap"      => R13Bitmap.`bitmap$0` = mode; io.y.addTag(R13Bitmap)
        case "serial"      => R13Serial.serialVersionUID = mode; io.y.addTag(R13Serial)
        case "lazy"        => if (mode == 1) R13Lazy.v; io.y.addTag(R13Lazy)
        case "annotated"   => io.y.addTag(R13Annotated)
        case "const"       => io.y.addTag(if (mode == 0) R13Const0 else R13Const1)
        case "traitBitmap" => R13TraitBitmap.`bitmap$0` = mode; io.y.addTag(R13TraitBitmap)
        case "caseBitmap"  => io.y.addTag(R13CaseBitmap(0))
        case "constAttr"   => io.y.addTag(new R13ConstAttribute)
      }
  }
}
class Round13Order0 extends Round13Design("order", 0)
class Round13Order1 extends Round13Design("order", 1)
class Round13Bitmap0 extends Round13Design("bitmap", 0)
class Round13Bitmap1 extends Round13Design("bitmap", 1)
class Round13Serial0 extends Round13Design("serial", 0)
class Round13Serial1 extends Round13Design("serial", 1)

// Round 14 (/tmp/review14-a/Attack14.scala): the encoder read a case-class tag through
// `productIterator` (and checked its shape with `productElementNames`), which the class can override:
// `R14Hidden(0)` and `R14Hidden(1)` had one key. Below: every user-overridable method the encoder
// called on a tag payload (Product hooks, `toString` of a non-final number class, a collection's
// iteration in a class that only claims to be the Scala library's, the accessors of a subclass of a
// Spinal tag the encoder special-cases).
case class R14Hidden(x: Int) extends SpinalTag { override def productIterator: Iterator[Any] = Iterator(0) }
trait R14ProductNames { def productElementNames: Iterator[String] }
case class R14Element(x: Int) extends SpinalTag with R14ProductNames {
  override def productElement(n: Int): Any = 0
  override def productElementNames: Iterator[String] = Iterator("x")
}
case class R14Body(x: Int) extends SpinalTag { val y: Int = x * 2 } // a field beyond its elements
class R14BigInteger(v: BigInt) extends java.math.BigInteger(v.toString) {
  override def toString: String = "0"
  override def toString(radix: Int): String = "0"
}
class R14JBigDecimal(v: Int) extends java.math.BigDecimal(v) { override def toString: String = "0" }
class R14EnableTag(override val clockDomain: ClockDomain, val extra: Int) extends ClockEnableTag(clockDomain)
class R14Driver(d: Data, val extra: Int) extends ExternalDriverTag(d)
class R14Mapping(n: String, r: Range, val extra: Int) extends MemSymbolesMapping(n, r)
class R14Domain(c: Bool, val extra: Int) extends ClockDomain(c)
class Round14Design(kind: String, mode: Int) extends Component {
  setDefinitionName("Round14")
  val io = new Bundle { val a = in Bool(); val y = out Bool() }
  io.y := io.a
  private val big = BigInt(1) << 80
  kind match {
    case "hidden"     => io.y.addTag(R14Hidden(mode))
    case "element"    => io.y.addTag(R14Element(mode))
    case "body"       => io.y.addTag(R14Body(mode))
    case "bigInteger" => io.y.addTag(AnyTag(new R14BigInteger(big + mode)))
    case "bigInt"     => io.y.addTag(AnyTag(BigInt(new R14BigInteger(big + mode))))
    case "bigDecimal" => io.y.addTag(AnyTag(BigDecimal(new R14JBigDecimal(mode))))
    case "fakeSeq"    => io.y.addTag(AnyTag(new scala.r14probe.FakeSeq(mode)))
    case "driver"     => io.y.addTag(new R14Driver(io.a, mode))
    case "mapping"    => io.y.addTag(MemSymbolesTag(Seq(new R14Mapping("s0", 0 until 4, mode))))
    case "domain"     => io.y.addTag(AnyTag(new R14Domain(ClockDomain.current.clock, mode)))
  }
}
/** A generated register read only as a clock enable, carrying a subclass of Spinal's `ClockEnableTag`
  * that names its own domain (the case the encoder writes as `:self`) and adds a field. */
class R14EnableDesign(mode: Int) extends Component {
  setDefinitionName("R14Enable")
  val io = new Bundle { val en = in Bool(); val y = out UInt(8 bits) }
  val boot = ClockDomain.current.copy(reset = null, config = ClockDomainConfig(resetKind = BOOT))
  def domain(): ClockDomain = { // an unnamed (generated) enable register
    val en = RegNext(!io.en)
    val d = boot.copy(clockEnable = en)
    // Spinal put its own `ClockEnableTag(d)` on `en`; a subclass equal to it would not be added (case
    // class equality), so it replaces it.
    en.removeTag(ClockEnableTag(d))
    en.addTag(new R14EnableTag(d, mode))
    d
  }
  val area = new ClockingArea(boot) {
    val inner = new ClockingArea(domain()) { val r = Reg(UInt(8 bits)) init 0; r := r + 1; io.y := r }
  }
}
class Round14Hidden0 extends Round14Design("hidden", 0)
class Round14Hidden1 extends Round14Design("hidden", 1)

/** Fixtures for rvw/tests/data/regen.sh: `$SPINALDB_FIXTURE_DIR/inc<n>/External.v` includes the
  * header next to it, whose `K` is the only difference. */
class IncludeFixture(n: Int) extends IncludeTop(sys.env.getOrElse("SPINALDB_FIXTURE_DIR", "/nonexistent") + s"/inc$n/External.v")
class Include0 extends IncludeFixture(0)
class Include1 extends IncludeFixture(1)

/** End-to-end: elaborate small designs, write the database, read it back with plain SQL. */
class SpinalDBSpec extends AnyFunSuite {
  private val repo  = new File("../..").getCanonicalFile
  private val roots = Seq(new File(repo, "SpinalTrace/examples/src"), new File(repo, "SpinalBlocks/spinalblocks/src/main/scala")).map(_.toPath)

  private def build(name: String, opts: DbOptions = DbOptions(), formal: Boolean = false)(gen: => Component): File = {
    val dir = Files.createTempDirectory(s"spinaldb-$name").toFile
    val out = new File(dir, s"$name.db")
    val config = SpinalConfig(targetDirectory = new File(dir, "rtl").getPath)
    SpinalDB.generate(if (formal) config.copy(mode = SystemVerilog).includeFormal else config, out,
      opts.copy(sourceRoots = roots, log = _ => ()))(gen)
    out
  }

  private def rows(db: File, sql: String): Seq[Seq[String]] = {
    val c = DriverManager.getConnection("jdbc:sqlite:" + db.getAbsolutePath)
    try {
      val rs  = c.createStatement().executeQuery(sql)
      val n   = rs.getMetaData.getColumnCount
      val out = ArrayBuffer[Seq[String]]()
      while (rs.next()) out += (1 to n).map(i => rs.getString(i))
      out.toSeq
    } finally c.close()
  }

  private lazy val gcd     = build("gcd")(new spinaltrace.examples.GCD)
  private lazy val cluster = build("cluster")(new spinalblocks.examples.GcdCluster)

  test("round 16: package names cannot make user expressions trusted") {
    assert(!ExprText.modelled(classOf[Round16Literal]))
    val keys = for (mode <- 0 to 1) yield {
      Round16LiteralState.mode = mode
      val db = build(s"r16literal$mode", probe)(new Round16LiteralDesign)
      val rtl = new String(Files.readAllBytes(db.toPath.getParent.resolve("rtl/Round16Literal.v")))
      assert(rtl.contains(if (mode == 0) "8'h01" else "8'h02"), rtl)
      rows(db, "SELECT key FROM assignments WHERE kind = 'data'").flatten
    }
    assert(keys.forall(_.exists(ExprText.isIncomplete)), keys)
  }

  test("round 16: ignored tags require exact classes even under another classloader") {
    val original = unusedTag.getClass
    val bytes = {
      val in = original.getResourceAsStream("/" + original.getName.replace('.', '/') + ".class")
      try in.readAllBytes() finally in.close()
    }
    // Give the copy the real jar's code source too: source alone cannot establish class identity.
    val loader = new ClassLoader(original.getClassLoader) {
      def copyClass(): Class[_] = defineClass(original.getName, bytes, 0, bytes.length, original.getProtectionDomain)
    }
    val copy = loader.copyClass()
    assert(!LibraryClasses.isSpinal(copy))
    assert(LibraryClasses.isSpinal(original))
    val ctor = copy.getDeclaredConstructor(); ctor.setAccessible(true)
    val fake = ctor.newInstance().asInstanceOf[SpinalTag]
    class Tagged extends Component { val y = out Bool(); y := True; y.addTag(fake) }
    val db = build("r16ignored", probe)(new Tagged)
    assert(rows(db, "SELECT tags FROM signals WHERE path = 'y'").flatten.exists(_ != null))
  }

  test("round 16: user classes in scala packages keep constant tag payloads") {
    val sig = Extractor.scalaSig(classOf[scala.r16probe.ConstTag]).get
    assert(sig.constants.contains("payload" -> 16), sig)
  }

  test("round 16: only library singletons may use labels without payloads") {
    assert(ExprText.isIncomplete(KeyEnc.label(Round16LiteralState)))
    assert(KeyEnc.label(ASYNC) == "ASYNC")
  }

  test("round 15: numeric payloads cannot hide behind a radix formatter") {
    class Liar(n: Int) extends java.math.BigInteger(n.toString) {
      override def toString(radix: Int): String = "0"
    }
    def number(n: Int): BigInt = new BigInt(new Liar(n))
    class Numeric(kind: String) extends Component {
      val io = new Bundle { val a = in Bool(); val y = out Bits(4 bits) }
      kind match {
        case "literal" => io.y := B(number(1), 4 bits)
        case "poison" => SpinalDBTestHooks.assignPoisonedBig(io.y, BigInt(1), number(2))
        case "memory" =>
          val m = Mem(Bits(4 bits), 2)
          m.initBigInt(Seq(number(1), BigInt(0)))
          io.y := m.readAsync(io.a.asUInt)
      }
    }
    for (kind <- Seq("literal", "poison", "memory")) {
      val db = build(s"r15$kind", probe)(new Numeric(kind))
      val query = if (kind == "memory") "SELECT key FROM memories" else
        "SELECT key FROM assignments WHERE target_id = (SELECT id FROM signals WHERE path = 'io_y')"
      assert(rows(db, query).flatten.exists(ExprText.isIncomplete), kind)
    }
    val e = new SpinalEnum { val a, b = newElement() }
    val enc = SpinalEnumEncoding("liar", i => number(i + 1))
    assert(ExprText.isIncomplete(ExprText.enumDefinition(e, enc)))
  }

  test("round 15: effective emission settings are stored independently of netlist keys") {
    class Poison extends Component { val y = out Bits(4 bits); y.assignDontCare() }
    val keys = for (zero <- Seq(false, true)) yield {
      val dir = Files.createTempDirectory("spinaldb-r15config").toFile
      val db = new File(dir, "design.db")
      SpinalDB.generate(SpinalConfig(targetDirectory = new File(dir, "rtl").getPath,
        dontCareGenAsZero = zero), db, probe)(new Poison)
      val values = rows(db, "SELECT value FROM meta WHERE key = 'emission_config'")
      assert(values.size == 1)
      assert(!ExprText.isIncomplete(values.head.head))
      values.head.head
    }
    assert(keys.distinct.size == 2)
  }

  test("round 15: emission config audit covers backend policies and refuses unknown payloads") {
    class Empty extends Component { val y = out Bool(); y := True }
    def emitted(change: SpinalConfig => SpinalConfig): String = {
      val dir = Files.createTempDirectory("spinaldb-r15audit").toFile
      val report = SpinalDB.elaborate(change(SpinalConfig(targetDirectory = dir.getPath)), traceNaming = false)(new Empty)
      EmissionConfig.key(report)
    }
    val base = emitted(identity)
    val policies: Seq[SpinalConfig => SpinalConfig] = Seq(
      _.copy(mode = SystemVerilog), _.copy(defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC)),
      _.copy(mergeAsyncProcess = true), _.copy(inlineRom = true),
      _.copy(noRandBoot = true), _.copy(randBootFixValue = false),
      _.copy(defaultClockDomainFrequency = FixedFrequency(50 MHz)), _.copy(device = Device.XILINX))
    // Use the selected SDK's constructor layout for optional backend flags.
    import scala.reflect.runtime.universe._
    val parameters = typeOf[SpinalConfig].typeSymbol.asClass.primaryConstructor.asMethod.paramLists.flatten.map(_.name.toString)
    val optional = Seq("mergeSyncProcess" -> false, "caseRom" -> true).flatMap { case (name, value) =>
      val index = parameters.indexOf(name)
      if (index < 0) { info(s"The selected SpinalHDL has no $name policy."); None }
      else Some((c: SpinalConfig) => {
        val args = c.productIterator.map(_.asInstanceOf[AnyRef]).toArray
        args(index) = Boolean.box(value)
        c.getClass.getConstructors.find(_.getParameterCount == args.length).get
          .newInstance(args: _*).asInstanceOf[SpinalConfig]
      })
    }
    assert(!ExprText.isIncomplete(base), base)
    for (change <- policies ++ optional) {
      val key = emitted(change)
      assert(!ExprText.isIncomplete(key) && key != base, key)
    }
    assert(emitted(_.copy(oneFilePerComponent = true)) == base)
    assert(!ExprText.isIncomplete(emitted { c => c.phasesInserters += (_ => ()); c }))
    assert(ExprText.isIncomplete(emitted { c => c.flags += new Object(); c }))
    assert(ExprText.isIncomplete(EmissionConfig.key(new SpinalReport[Component]())))
  }

  test("meta, schema and artifacts from the same elaboration") {
    val meta = rows(gcd, "SELECT key, value FROM meta").map(r => r(0) -> r(1)).toMap
    assert(meta("schema") == Schema.Version && meta("toplevel") == "GCD")
    assert(rows(gcd, "SELECT name FROM artifacts ORDER BY name").map(_.head) == Seq("blocks.json", "hgldd/GCD.dd", "pdg.json"))
    assert(rows(gcd, "SELECT count(*) FROM pdg_vertices").head.head == "0") // tables are opt-in
    assert(rows(gcd, "SELECT count(*) FROM rtl_files").head.head.toInt >= 1)
  }

  test("signals: kinds, directions, Spinal paths, pruning, source lines") {
    val s = rows(gcd, "SELECT path, kind, direction, spinal_path, pruned, generated, line FROM signals ORDER BY id")
      .map(r => r.head -> r.tail).toMap
    assert(s("x").take(2) == Seq("reg", null))
    assert(s("io_a").take(3) == Seq("wire", "in", "io.a"))
    assert(s("tmp")(3) == "1")                                 // pruned: unused
    assert(s("io_a")(5) == "8" && s("x")(5) == "15")           // Gcd.scala lines
    assert(rows(gcd, "SELECT clock_role FROM signals WHERE path = 'clk'").head.head == "clock")
  }

  test("assignments carry conditions and Scala locations") {
    val a = rows(gcd, "SELECT a.source, c.kind, c.expr, a.line FROM assignments a JOIN signals s ON s.id = a.target_id " +
      "LEFT JOIN conds c ON c.id = a.cond_id WHERE s.path = 'x' ORDER BY a.seq")
    assert(a == Seq(Seq("x - y", "when", "y < x", "20"), Seq("io_a", "when", "io_loadValues", "26")))
    val y = rows(gcd, "SELECT c.kind FROM assignments a JOIN signals s ON s.id = a.target_id JOIN conds c ON c.id = a.cond_id " +
      "WHERE s.path = 'y' ORDER BY a.seq").map(_.head)
    assert(y == Seq("else", "when"))
  }

  test("dependency edges, including self-dependencies and conditions") {
    val e = rows(gcd, "SELECT s1.path, s2.path, e.kind FROM edges e JOIN signals s1 ON s1.id = e.src JOIN signals s2 ON s2.id = e.dst")
      .map(r => (r(0), r(1), r(2))).toSet
    assert(e.contains(("io_a", "x", "data")) && e.contains(("x", "x", "data")) && e.contains(("io_loadValues", "x", "cond")))
    assert(e.contains(("x", "io_result", "data")))
  }

  test("hierarchy, registers with reset, memories, bundles and areas") {
    assert(rows(cluster, "SELECT path FROM components ORDER BY path").map(_.head) == Seq("", "fifo", "units_0", "units_1"))
    assert(rows(cluster, "SELECT reset_value FROM signals WHERE path = 'units_0.x'").head.head == "0")
    assert(rows(cluster, "SELECT reset_value FROM signals WHERE path = 'ctrl_fsm_stateReg'").head.head.endsWith(".BOOT"))
    val m = rows(cluster, "SELECT m.path, m.width, m.depth FROM memories m ORDER BY m.path")
    assert(m.contains(Seq("fifo.logic_ram", "32", "4")))
    val ports = rows(cluster, "SELECT p.kind FROM mem_ports p JOIN memories m ON m.id = p.memory_id WHERE m.path = 'fifo.logic_ram'").map(_.head)
    assert(ports.toSet == Set("write", "read_sync"))
    assert(rows(cluster, "SELECT class_name, direction FROM bundles WHERE path = 'io.cmd'").head == Seq("Stream", "in/out"))
    assert(rows(cluster, "SELECT path FROM areas a WHERE a.path = 'logic.ptr'").nonEmpty)
    // Locations never point into SpinalDB's own entry code; user components at their class body
    assert(!rows(cluster, "SELECT path FROM files").exists(_.head.contains("spinaldb")))
    assert(rows(cluster, "SELECT line FROM components WHERE path = 'units_0'").head.head == "10")
    assert(rows(cluster, "SELECT line FROM components WHERE path = 'fifo'").head.head == "43")  // spinal.lib: instantiation
    val cd = rows(cluster, "SELECT clock, reset, reset_kind FROM clock_domains")
    assert(cd == Seq(Seq("clk", "reset", "ASYNC")))
  }

  test("--no-pdg elaborates without SpinalTrace's naming phase") {
    val db = build("plain", DbOptions(pdg = false))(new spinaltrace.examples.GCD)
    assert(!rows(db, "SELECT name FROM artifacts").map(_.head).contains("pdg.json"))
    assert(rows(db, "SELECT count(*) FROM signals WHERE name LIKE 'when\\_%' ESCAPE '\\'").head.head.toInt <= 1)
  }

  test("signals of unnamed Vecs keep their RTL path as Spinal path (no bogus `io` root)") {
    val db = build("loop")(new LoopVecs)
    val bad = rows(db, "SELECT path, spinal_path FROM signals WHERE direction IS NULL AND spinal_path LIKE 'io.%'")
    assert(bad.isEmpty, bad.mkString(", "))
    assert(rows(db, "SELECT count(*) FROM bundles WHERE path = 'io'").head.head == "1")
  }

  private val probe = DbOptions(pdg = false, blocks = false, hgldd = false)

  test("typed keys tell signed from unsigned shifts that render the same text") {
    val a = build("unsigned", probe)(new CastDesign(false))
    val b = build("signed", probe)(new CastDesign(true))
    val q = "SELECT a.source, a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y' AND a.kind = 'data'"
    val (ra, rb) = (rows(a, q).head, rows(b, q).head)
    assert(ra(0) == rb(0), "display text is the same (`io_a >> 3`)")
    assert(ra(1) != rb(1) && rb(1).contains("SInt") && !ra(1).contains("SInt"))
    assert(rows(a, "SELECT value FROM meta WHERE key = 'schema'").head.head == "rvw.designdb/20")
  }

  test("memory init contents are recorded") {
    val q = "SELECT init_sha256, init_words FROM memories"
    val (r1, r2) = (rows(build("rom1", probe)(new RomDesign(1)), q).head, rows(build("rom2", probe)(new RomDesign(2)), q).head)
    assert(r1(1) == "4" && r1(0) != null && r1(0) != r2(0))
    assert(rows(build("ram", probe)(new MaskDesign), q).head == Seq(null, null))
  }

  test("memory write masks are dependencies and recorded on the write") {
    val db = build("masked", probe)(new MaskDesign)
    val w = rows(db, "SELECT a.mask, a.key FROM assignments a WHERE a.kind = 'mem_write'").head
    assert(w(0) == "io_mask" && w(1).contains("io_mask"))
    assert(rows(db, "SELECT e.kind FROM edges e JOIN signals s ON s.id = e.src JOIN signals d ON d.id = e.dst " +
      "WHERE s.path = 'io_mask' AND d.path = 'mem'") == Seq(Seq("cond")))
    assert(rows(db, "SELECT count(*) FROM assign_reads r JOIN signals s ON s.id = r.signal_id WHERE s.path = 'io_mask'").head.head == "1")
  }

  test("a multi-driver temporary (mux result) is keyed by its own assignments") {
    val q = "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y' AND a.kind = 'data'"
    val (k2, k3) = (rows(build("mux2", probe)(new MuxDesign(2)), q).head.head, rows(build("mux3", probe)(new MuxDesign(3)), q).head.head)
    assert(k2 != k3, s"mux constant 2 vs 3 must change the key: $k2")
    assert(k2 == rows(build("mux2b", probe)(new MuxDesign(2)), q).head.head, "same design, same key")
  }

  test("a pure line shift keeps keys; a changed `when` condition changes them") {
    def keys(db: File) = rows(db, "SELECT s.path, a.key FROM assignments a JOIN signals s ON s.id = a.target_id " +
      "WHERE s.path NOT LIKE 'when\\_%' ESCAPE '\\' ORDER BY a.seq") ++ rows(db, "SELECT kind, key FROM conds ORDER BY id")
    val (a, b, c) = (keys(build("shiftA", probe)(new ShiftA)), keys(build("shiftB", probe)(new ShiftB)), keys(build("shiftC", probe)(new ShiftC)))
    assert(!a.flatten.exists(k => k != null && k.contains("when_")), a.mkString("\n"))
    assert(a == b)
    assert(a != c)
  }

  test("clock-enable and soft-reset polarity are part of the clock domain") {
    val q = "SELECT clock_enable, clock_enable_active_high, soft_reset, soft_reset_active_high FROM clock_domains"
    assert(rows(build("enHigh", probe)(new PolarityDesign(false, false)), q).head == Seq("io_en", "true", null, null))
    assert(rows(build("enLow", probe)(new PolarityDesign(false, true)), q).head == Seq("io_en", "false", null, null))
    assert(rows(build("softHigh", probe)(new PolarityDesign(true, false)), q).head == Seq(null, null, "io_en", "true"))
    assert(rows(build("softLow", probe)(new PolarityDesign(true, true)), q).head == Seq(null, null, "io_en", "false"))
  }

  test("generated registers keep their operand position in typed keys") {
    val q = "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y' AND a.kind = 'data'"
    val (ka, kb) = (rows(build("swapA", probe)(new SwapDesign(false)), q).head.head,
      rows(build("swapB", probe)(new SwapDesign(true)), q).head.head)
    assert(ka != kb, s"a - b and b - a of two RegNext must differ: $ka")
    assert(ka == rows(build("swapA2", probe)(new SwapDesign(false)), q).head.head, "same design, same key")
  }

  test("generated register chains keep operand position at any depth") {
    val q = "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y' AND a.kind = 'data'"
    for (n <- Seq(4, 5, 6, 12)) {
      val (ka, kb) = (rows(build(s"deep${n}a", probe)(new DeepSwapDesign(false, n)), q).head.head,
        rows(build(s"deep${n}b", probe)(new DeepSwapDesign(true, n)), q).head.head)
      assert(ka != kb, s"$n stages: a - b and b - a must differ: $ka")
      assert(!ExprText.isIncomplete(ka) && !ExprText.isIncomplete(kb), ka)
      assert(ka == rows(build(s"deep${n}a2", probe)(new DeepSwapDesign(false, n)), q).head.head, "same design, same key")
    }
  }

  test("loops of generated registers are keyed by canonical ids") {
    val q = "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y' AND a.kind = 'data'"
    val all = "SELECT a.key FROM assignments a ORDER BY a.seq"
    for (dense <- Seq(false, true)) {
      val (la, lb) = (build(s"loopA$dense", probe)(new LoopDesign(false, 6, dense)), build(s"loopB$dense", probe)(new LoopDesign(true, 6, dense)))
      val (ka, kb) = (rows(la, q).head.head, rows(lb, q).head.head)
      assert(ka != kb, s"swapped loop operands must differ: $ka")
      assert(!rows(la, all).flatten.exists(ExprText.isIncomplete), rows(la, all).mkString("\n"))
      assert(rows(la, all) == rows(build(s"loopA2$dense", probe)(new LoopDesign(false, 6, dense)), all), "same design, same keys")
      assert(rows(build(s"loopC$dense", probe)(new LoopDesign(false, 5, dense)), q).head.head != ka, "a shorter loop differs")
    }
  }

  test("a generated clock enable is compared by its logic") {
    val q = "SELECT clock_enable_key FROM clock_domains WHERE clock_enable IS NOT NULL"
    val (k1, k2) = (rows(build("enLogic1", probe)(new EnableLogicDesign(1)), q), rows(build("enLogic2", probe)(new EnableLogicDesign(2)), q))
    assert(k1.size == 1 && k1 != k2, s"clockEnable = io.a > 1 vs > 2 must differ: $k1")
    assert(k1.head.head.contains("io_a"), k1)
    assert(k1 == rows(build("enLogic1b", probe)(new EnableLogicDesign(1)), q), "same design, same key")
  }

  test("distinct generated registers with equal drivers stay distinct") {
    val q = "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y' AND a.kind = 'data'"
    val (k0, k1) = (rows(build("sharing0", probe)(new SharingDesign(0)), q).head.head, rows(build("sharing1", probe)(new SharingDesign(1)), q).head.head)
    assert(k0 != k1, s"(r - r) - s and (r - s) - s must differ: $k0")
    assert(k0 == rows(build("sharing0b", probe)(new SharingDesign(0)), q).head.head, "same design, same key")
  }

  test("a register loop larger than the limit gives an incomplete key") {
    def keyOfY(limit: Int, n: Int): String = {
      val top = SpinalConfig(targetDirectory = Files.createTempDirectory("spinaldb-limit").toString)
        .generateVerilog(new LoopDesign(false, n)).toplevel
      var src: spinal.core.internals.Expression = null
      top.io.y.foreachStatements { case a: spinal.core.internals.DataAssignmentStatement => src = a.source; case _ => }
      new ExprText((bt, _) => bt.getName(), spinaltrace.Netlist.isGenerated, loopLimit = limit).key(src, top)
    }
    assert(!ExprText.isIncomplete(keyOfY(6, 6)))
    assert(ExprText.isIncomplete(keyOfY(5, 6)), keyOfY(5, 6))
  }

  test("round 8: memory port policies and BlackBox generics are keyed; unmodelled nodes are incomplete") {
    val ports = "SELECT key FROM mem_ports ORDER BY id"
    val Seq(r0, r1, r2, r3) = (0 to 3).map(m => rows(build(s"rw$m", probe)(new RwDesign(m)), ports))
    assert(Seq(r0, r1, r2, r3).distinct.size == 4, s"readFirst/writeFirst/dontCare and doRead/dontRead must differ: $r0 $r1 $r2 $r3")
    assert(r0.head.head.contains("rw=readFirst") && r0.head.head.contains("dw=doRead"), r0)
    assert(!r0.flatten.exists(ExprText.isIncomplete), r0)
    assert(rows(build("rw0b", probe)(new RwDesign(0)), ports) == r0, "same design, same key")
    val bb = "SELECT generics, body_sha256, key FROM blackboxes"
    val (b1, b2) = (rows(build("bb1", probe)(new BoxDesign(1)), bb).head, rows(build("bb2", probe)(new BoxDesign(2)), bb).head)
    assert(b1(0) == "K=Int 1" && b2(0) == "K=Int 2", b1)
    assert(b1(1) == null && ExprText.isIncomplete(b1(2)), "no external body: incomplete")
    val v = Files.createTempFile("external", ".v")
    Files.write(v, "module External #(parameter K=1)(input [7:0] a, output [7:0] y); assign y = a + K; endmodule\n".getBytes)
    val withRtl = rows(build("bbrtl", probe)(new BoxDesign(1, v.toString)), bb).head
    assert(withRtl(1) != null && !ExprText.isIncomplete(withRtl(2)), withRtl)
    val supplied = rows(build("bbuser", probe.copy(blackboxSources = Map("External" -> Seq(v))))(new BoxDesign(1)), bb).head
    assert(supplied(1) == withRtl(1), "the same body hashes the same, from addRTLPath or --blackbox-source")
    // Allow-list: a node class the key does not model gives `$incomplete:`, never a plain key.
    val y = "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y' AND a.kind = 'data'"
    val (plain, salted) = (rows(build("plainNot", probe)(new UnsupportedDesign(0)), y).head.head,
      rows(build("saltedNot", probe)(new UnsupportedDesign(3)), y).head.head)
    assert(!ExprText.isIncomplete(plain) && ExprText.isIncomplete(salted) && salted.contains("SaltedNot"), salted)
    // An operand the node's walk skips (as `SuffixExpression.target`) is not in the key: incomplete.
    val hidden = rows(build("hiddenNot", probe)(new Component {
      val io = new Bundle { val a, b = in Bits(8 bits); val y = out Bits(8 bits) }
      io.y := SpinalDBTestHooks.hiddenNot(io.a, io.b)
    }), y).head.head
    assert(ExprText.isIncomplete(hidden) && hidden.contains("HiddenOperandNot"), hidden)
  }

  test("round 8: init and initial differ; poisoned literals and enum encodings are keyed") {
    val q = "SELECT a.kind, a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'r' ORDER BY a.seq"
    val (i, ii) = (rows(build("init", probe)(new InitialDesign(false)), q), rows(build("initial", probe)(new InitialDesign(true)), q))
    assert(i.map(_.head).contains("init") && ii.map(_.head).contains("initial"), (i, ii))
    val y = "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y' AND a.kind = 'data'"
    val (p0, p1) = (rows(build("poison0", probe)(new PoisonDesign(0)), y), rows(build("poison1", probe)(new PoisonDesign(1)), y))
    assert(p0 != p1, s"1x0x and 0x1x must differ: $p0")
    val t = "SELECT s.type, s.width FROM signals s WHERE s.path = 't'"
    val (e0, e1) = (rows(build("enumSeq", probe)(new EnumCastDesign(false)), t), rows(build("enumGray", probe)(new EnumCastDesign(true)), t))
    assert(e0 != e1 && e0.head(1) == e1.head(1), s"binary and Gray code of one enum must differ: $e0 $e1")
  }

  test("round 9: enums are keyed by element order and encoded values") {
    val q = "SELECT s.type, (SELECT group_concat(a.key, ' | ') FROM assignments a WHERE a.target_id = s.id) FROM signals s WHERE s.path = 'state_1'"
    var captured: SpinalEnum = null
    val Seq(c0, c1, o0, o1) = Seq[(String, () => EnumOrderDesign)](("c0", () => new EnumCustom0), ("c1", () => new EnumCustom1),
      ("o0", () => new EnumOrder0), ("o1", () => new EnumOrder1))
      .map { case (n, d) => rows(build(s"enum9$n", probe)({ val x = d(); captured = x.e; x }), q).head }
    assert(c0(0) == "State@custom[2]{a=0,b=1,c=2}" && c1(0) == "State@custom[2]{a=1,b=2,c=0}", (c0, c1))
    assert(o0(0) == "State@seq[2]{a=0,b=1,c=2}" && o1(0) == "State@seq[2]{b=0,a=1,c=2}", (o0, o1))
    assert(c0(1) != c1(1) && o0(1) != o1(1), s"assignment keys must differ: $c0 $c1 $o0 $o1")
    assert(Seq(c0, c1, o0, o1).flatten.forall(k => !ExprText.isIncomplete(k)))
    assert(rows(build("enum9c1b", probe)(new EnumCustom1), q).head == c1, "same design, same keys")
    // An encoding whose values cannot be evaluated is incomplete, never a name.
    val broken = new SpinalEnumEncoding {
      override def getWidth(senum: SpinalEnum): Int = 2
      override def getValue[T <: SpinalEnum](element: SpinalEnumElement[T]): BigInt = throw new IllegalStateException("no value")
      override def getElement[T <: SpinalEnum](element: BigInt, senum: T): SpinalEnumElement[T] = ???
      override def isNative = false
    }.setName("broken")
    assert(ExprText.isIncomplete(ExprText.enumDefinition(captured, broken)), ExprText.enumDefinition(captured, broken))
  }

  test("round 9: a BlackBox body is fingerprinted with every file it includes") {
    val dir = Files.createTempDirectory("spinaldb-inc")
    val header = dir.resolve("external.svh")
    val ext = dir.resolve("External.v")
    def body(text: String) = Files.write(ext, text.getBytes)
    body(s"""`include "$header"
module External #(parameter K=1)(input [7:0] a, output [7:0] y); assign y = a + `K + K; endmodule
""")
    val bb = "SELECT body_sha256, key, body_from FROM blackboxes"
    def at(k: Int, gen: Int = 1) = {
      Files.write(header, s"`define K $k\n".getBytes)
      rows(build(s"inc$k", probe)(new IncludeTop(ext.toString, gen)), bb).head
    }
    val (k1, k2, k1b) = (at(1), at(2), at(1))
    assert(k1(0) != null && !ExprText.isIncomplete(k1(1)) && k1(2).contains("include " + header), k1)
    assert(k1(0) != k2(0), s"the included header's K changed: $k1 $k2")
    assert(k1b == k1, "same files, same fingerprint")
    // Nested include, relative to the including file.
    Files.write(header, "`include \"inner.svh\"\n".getBytes)
    Files.write(dir.resolve("inner.svh"), "`define K 3\n".getBytes)
    val nested = rows(build("incNested", probe)(new IncludeTop(ext.toString)), bb).head
    assert(nested(0) != null && nested(2).contains("inner.svh"), nested)
    Files.write(dir.resolve("inner.svh"), "`define K 4\n".getBytes)
    assert(rows(build("incNested2", probe)(new IncludeTop(ext.toString)), bb).head(0) != nested(0), "nested include changed")
    // What cannot be determined is incomplete: a missing include, a module not defined by the body
    // under its generics, an elaboration-time file read, a VHDL body.
    def incomplete(name: String, text: String, gen: Int = 1, file: java.nio.file.Path = ext): String = {
      Files.write(file, text.getBytes)
      val r = rows(build(name, probe)(new IncludeTop(file.toString, gen)), bb).head
      assert(r(0) == null && ExprText.isIncomplete(r(1)), r)
      r(1)
    }
    assert(incomplete("incMissing", "`include \"/nonexistent/x.svh\"\nmodule External(input [7:0] a, output [7:0] y); assign y = a; endmodule\n")
      .contains("input_not_captured"))
    val sub = "module External #(parameter K=1)(input [7:0] a, output [7:0] y);\n generate if (K == 7) begin: g Sub s(); end endgenerate\n assign y = a; endmodule\n"
    Files.write(ext, sub.getBytes)
    assert(rows(build("incSubDefault", probe)(new IncludeTop(ext.toString)), bb).head(0) != null, "K=1 needs no Sub")
    assert(incomplete("incSub", sub, gen = 7).contains("Sub"))
    assert(incomplete("incRead", "module External(input [7:0] a, output [7:0] y); reg [7:0] m [0:1];\n initial $readmemh(\"/dev/null\", m);\n assign y = a; endmodule\n")
      .contains("readmemh"))
    assert(incomplete("incVhdl", "entity External is end;\n", file = dir.resolve("External.vhd")).contains("VHDL"))
  }

  test("round 9: tag payloads and attribute files are keyed by content") {
    val q = "SELECT tags FROM signals WHERE path = 'io_y'"
    def tags(name: String, mode: String, file: String = null) = rows(build(name, probe)(new TagDesign(mode, file)), q).head.head
    val (high, low) = (tags("tagHigh", "high"), tags("tagLow", "low"))
    assert(high != low && !ExprText.isIncomplete(high), s"two clock domains with one clock name: $high $low")
    val (c1, c2) = (tags("tagCase1", "case1"), tags("tagCase2", "case2"))
    assert(c1 != c2 && c1.contains("CaseTag(k=Int(1))") && !ExprText.isIncomplete(c1), (c1, c2))
    assert(ExprText.isIncomplete(tags("tagHidden", "hidden")), "a payload toString does not print is not modelled")
    val f = Files.createTempFile("init", ".hex")
    Files.write(f, "00\n".getBytes)
    val f0 = tags("tagFile0", "file", f.toString)
    Files.write(f, "01\n".getBytes)
    val f1 = tags("tagFile1", "file", f.toString)
    assert(f0 != f1 && f0.contains("contents") && !ExprText.isIncomplete(f0), (f0, f1))
    assert(ExprText.isIncomplete(tags("tagFileMissing", "file", "/nonexistent/init.hex")))
    val (s1, s2) = (tags("tagSym1", "symbols1"), tags("tagSym2", "symbols2"))
    assert(s1 != s2 && s1.contains("\"s0\":Range(0,4,1,false)") && !ExprText.isIncomplete(s1), (s1, s2))
  }

  test("round 10: a switch default is keyed by every case key; overlapping cases by the earlier keys") {
    val conds = "SELECT kind, key FROM conds ORDER BY id"
    def c(name: String)(gen: => Component) = rows(build(name, probe)(gen), conds)
    val (d0, d1) = (c("default0")(new Default0), c("default1")(new Default1))
    assert(d0 != d1, s"is(0) {} default vs is(1) {} default must differ: $d0")
    assert(d0.exists(r => r.head == "default" && r(1).contains("|not{")), d0)
    assert(d0 == c("default0b")(new Default0), "same design, same keys")
    // The same switch driving a compiler temporary: its `$gen` key holds the case keys.
    val q = "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y' AND a.kind = 'data'"
    val (t0, t1) = (rows(build("defTemp0", probe)(new DefaultTemp0), q), rows(build("defTemp1", probe)(new DefaultTemp1), q))
    assert(t0 != t1 && t0.head.head.contains("$gen:") && !t0.flatten.exists(ExprText.isIncomplete), s"$t0 $t1")
    val (o0, o1) = (c("overlap0")(new Overlap0), c("overlap1")(new Overlap1))
    assert(o0.toSet != o1.toSet, s"swapped overlapping cases must differ: $o0")
    assert(o0.exists(r => r.head == "case" && r(1).contains("|not{")), o0)
    // Exclusive literal keys keep the plain case key: an earlier case cannot block a later one.
    assert(d0.filter(_.head == "case").forall(r => !r(1).contains("not{")), d0)
  }

  test("round 10: tags of a generated register read only as a clock enable are keyed") {
    val q = "SELECT clock_enable_key FROM clock_domains WHERE clock_enable IS NOT NULL"
    def k(name: String)(gen: => Component) = rows(build(name, probe)(gen), q)
    val (k0, k1) = (k("tagClock0")(new TagClock0), k("tagClock1")(new TagClock1))
    assert(k0.size == 1 && k0 != k1, s"an init attribute 0 vs 1 on the enable register must differ: $k0")
    assert(!k0.flatten.exists(ExprText.isIncomplete), k0)
    assert(k0 == k("tagClock0b")(new TagClock0), "same design, same key")
    assert(k("tagClockPlain")(new TagClockDesign("plain")) != k0, "an attribute is a difference")
    val hidden = k("tagClockHidden")(new TagClockHidden)
    assert(hidden.flatten.exists(ExprText.isIncomplete), s"an unreadable tag payload is incomplete: $hidden")
  }

  test("round 10: component instance and definition attributes are keyed") {
    val q = "SELECT path, tags FROM components ORDER BY path"
    val (a0, a1, a2) = (rows(build("compAttr0", probe)(new CompAttr0), q), rows(build("compAttr1", probe)(new CompAttr1), q),
      rows(build("compAttr2", probe)(new CompAttr2), q))
    assert(a0 == Seq(Seq("", null), Seq("c", null)), a0)
    assert(a1.find(_.head == "c").exists(_(1).contains("definition: attr string(\"keep_hierarchy\"=\"yes\")")), a1)
    assert(a2.find(_.head == "c").exists(_(1).contains("instance: attr string(\"dont_touch\"=\"true\")")), a2)
  }

  test("round 11: only names Spinal gave are line names; a user signal named like one is compared by name") {
    val q = "SELECT path, generated FROM signals WHERE path LIKE 'when\\_%' ESCAPE '\\' ORDER BY path"
    val n0 = build("namedRegs0", probe)(new NamedRegs0)
    assert(rows(n0, q) == Seq(Seq("when_Test_l12", "0"), Seq("when_Test_l13", "0"), Seq("when_Test_l14", "0")), rows(n0, q))
    val keys = "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_y'"
    val (k0, k1) = (rows(n0, keys), rows(build("namedRegs1", probe)(new NamedRegs1), keys))
    assert(k0 != k1 && k0.head.head.contains("when_Test_l12"), s"$k0 $k1")
    assert(rows(n0, "SELECT message FROM warnings").flatten.exists(_.contains("line name")))
    // Spinal's own `when` names stay generated without SpinalTrace's naming phase (--no-pdg).
    val shift = build("shiftA11", probe)(new ShiftA)
    assert(rows(shift, q).nonEmpty && rows(shift, q).forall(_(1) == "1"), rows(shift, q))
  }

  test("round 11: each component's emitted port order is stored") {
    val q = "SELECT name, direction, width, port_index FROM signals WHERE port_index IS NOT NULL ORDER BY port_index"
    val (p0, p1) = (rows(build("ports0", probe)(new PortOrder0), q), rows(build("ports1", probe)(new PortOrder1), q))
    assert(p0.map(_.head) == Seq("a", "b", "io_y") && p1.map(_.head) == Seq("b", "a", "io_y"), s"$p0 $p1")
    assert(p0.head == Seq("a", "in", "1", "0"), p0)
    // A Stream's `fire` (a suffix) is no port; the cluster's ports are numbered without gaps per component.
    val c = rows(cluster, "SELECT component_id, port_index FROM signals WHERE port_index IS NOT NULL ORDER BY component_id, port_index")
    c.groupBy(_.head).values.foreach(g => assert(g.map(_(1).toInt) == g.indices, g))
  }

  test("round 11: a Scala object tag is keyed by its fields") {
    val q = "SELECT tags FROM signals WHERE path = 'io_y'"
    def t(name: String, mode: Int) = rows(build(name, probe)(new ObjTagDesign(mode)), q).head.head
    val (t0, t1) = (t("objTag0", 0), t("objTag1", 1))
    assert(t0 != t1 && t0.contains("value=Int(0)") && !ExprText.isIncomplete(t0), s"$t0 $t1")
    assert(t("objTag2", 2) == "tag spinaldb.ObjStateless$:spinaldb.ObjStateless$")
    assert(ExprText.isIncomplete(t("objTag3", 3)), "a field that is not content is not modelled")
  }

  test("round 11: an assertion message is stored as written") {
    val q = "SELECT key FROM statements"
    val (a0, a1) = (rows(build("assert0", probe)(new AssertMsg0), q), rows(build("assert1", probe)(new AssertMsg1), q))
    assert(a0 != a1 && a0.head.head.contains("\"when_Test_l12\""), s"$a0 $a1")
  }

  private def r12(kind: String, mode: Int, q: String = "SELECT tags FROM signals WHERE path = 'io_y'"): String =
    rows(build(s"r12$kind$mode", probe)(new Round12Design(kind, mode)), q).map(_.mkString("|")).mkString("\n")

  test("round 12: an attribute subclass is keyed by its emitted eligibility, flags and fields") {
    val plain = r12("plain", 0)
    assert(!ExprText.isIncomplete(plain) && plain.contains("lang=[verilog,systemverilog,vhdl]"), plain)
    val (l0, l1) = (r12("lang", 0), r12("lang", 1))
    assert(l0 != l1 && !ExprText.isIncomplete(l0) && l1.contains("lang=[]"), s"$l0 $l1")
    val (f0, f1) = (r12("field", 0), r12("field", 1))
    assert(f0 != f1 && !ExprText.isIncomplete(f0) && f0.contains("k=Int(0)"), s"$f0 $f1")
    val io = r12("io", 0)
    assert(io != plain && io.contains("ioTag") && !ExprText.isIncomplete(io), io)
    assert(ExprText.isIncomplete(r12("assigned", 0)), "an override the keys do not evaluate is not modelled")
    assert(ExprText.isIncomplete(r12("ref", 0)), "a field that is not content is not modelled")
    val v = r12("verilator", 0)
    assert(!ExprText.isIncomplete(v) && v.contains("lang=[verilog,systemverilog]") && v.contains("COMMENT_ATTRIBUTE"), v)
    // The same rule for a memory's attributes (MemAttr.scala).
    val q = "SELECT key FROM memories"
    val (m0, m1) = (rows(build("r12mem0", probe)(new MemAttrDesign(0)), q), rows(build("r12mem1", probe)(new MemAttrDesign(1)), q))
    assert(m0 != m1 && !ExprText.isIncomplete(m0.head.head), s"$m0 $m1")
  }

  test("round 12: strings, numbers and collections in keys are typed and escaped") {
    val (s0, s1) = (r12("seq", 0), r12("seq", 1))
    assert(s0 != s1 && !ExprText.isIncomplete(s0), s"$s0 $s1")
    val (n0, n1) = (r12("num", 0), r12("num", 1))
    assert(n0 != n1 && n0.contains("Int(1)") && n1.contains("Long(1)"), s"$n0 $n1")
    // Control characters (the register-token marks of ExprText among them) are escaped, so a
    // string cannot pose as a token or as its own escaped form.
    val (c0, c1) = (r12("control", 0), r12("control", 1))
    assert(c0 != c1 && !c0.contains("\u0001"), s"$c0 $c1")
    // An unordered collection is written in a fixed order.
    assert(r12("set", 0) == r12("set", 1))
    val q = "SELECT key FROM statements"
    for (k <- Seq("assert", "assertSig", "assertFmt")) {
      val (a0, a1) = (r12(k, 0, q), r12(k, 1, q))
      assert(a0 != a1 && !ExprText.isIncomplete(a0), s"$k: $a0 $a1")
    }
  }

  test("round 12: a Scala object's `$`-named field is keyed") {
    val (d0, d1) = (r12("dollar", 0), r12("dollar", 1))
    assert(d0 != d1 && d0.contains("$payload=Int(0)") && !ExprText.isIncomplete(d0), s"$d0 $d1")
  }

  test("round 12: no key holds an identity hash (`Class@1b2c3d`); assertion parts have stable labels") {
    val identity = "[\\w$]@[0-9a-f]{1,8}(?![\\w$])".r
    val cols = Seq("assignments" -> "key", "conds" -> "key", "mem_ports" -> "key", "statements" -> "key", "memories" -> "key",
      "signals" -> "tags", "signals" -> "type", "components" -> "tags", "blackboxes" -> "key", "clock_domains" -> "reset_kind",
      "clock_domains" -> "clock_edge", "clock_domains" -> "clock_key", "clock_domains" -> "reset_key",
      "clock_domains" -> "clock_enable_key", "clock_domains" -> "soft_reset_key")
    val formal = build("r12formal", probe, formal = true)(new FormalKinds)
    val dbs = Seq(gcd, cluster, formal) ++ Seq("plain", "lang", "field", "io", "verilator", "dollar", "seq", "num", "assertSig")
      .map(k => build(s"r12id$k", probe)(new Round12Design(k, 0)))
    for (db <- dbs; (t, c) <- cols; v <- rows(db, s"SELECT $c FROM $t").flatten if v != null)
      assert(identity.findFirstIn(v).isEmpty, s"$t.$c in $db holds an identity hash: $v")
    val st = rows(formal, "SELECT key FROM statements ORDER BY id").map(_.head)
    for (w <- Seq("ASSERT", "ASSUME", "COVER", "NOTE", "WARNING", "ERROR", "FAILURE", "CLOCKED", "INITIAL"))
      assert(st.exists(_.contains(w)), s"$w: $st")
    assert(!st.exists(ExprText.isIncomplete), st)
    val z = rows(formal, "SELECT a.key FROM assignments a JOIN signals s ON s.id = a.target_id WHERE s.path = 'io_z'").head.head
    assert(z.contains("RANDOM_ANY_SEQ") && !ExprText.isIncomplete(z), z)
  }

  private def r13(kind: String, mode: Int, q: String = "SELECT tags FROM signals WHERE path = 'io_y'"): String =
    rows(build(s"r13$kind$mode", probe)(new Round13Design(kind, mode)), q).map(_.mkString("|")).mkString("\n")

  test("round 13: tags and attributes keep the order the emitters write them in") {
    val q = "SELECT tags FROM signals WHERE path = 'r'"
    val (o0, o1) = (r13("order", 0, q), r13("order", 1, q))
    assert(o0 != o1 && !ExprText.isIncomplete(o0), s"$o0 $o1")
    assert(o0.indexOf("Int(0)") < o0.indexOf("Int(1)") && o1.indexOf("Int(1)") < o1.indexOf("Int(0)"), s"$o0 $o1")
  }

  test("round 13: only fields the Scala compiler provably added are left out of a tag's key") {
    // A user's field named like compiler bookkeeping is keyed.
    for (k <- Seq("bitmap", "serial", "traitBitmap")) {
      val (d0, d1) = (r13(k, 0), r13(k, 1))
      assert(d0 != d1 && !ExprText.isIncomplete(d0), s"$k: $d0 $d1")
    }
    assert(r13("bitmap", 0).contains("bitmap$0=Int(0)") && r13("serial", 0).contains("serialVersionUID=Long(0)"))
    // A lazy val's bitmap is the compiler's: whether the lazy val was read does not change the key
    // (its field is keyed as it is), and `@SerialVersionUID`'s field is the compiler's.
    val lz = r13("lazy", 0)
    assert(!lz.contains("bitmap") && !ExprText.isIncomplete(lz) && lz.contains("v=Int("), lz)
    val privateUid = java.lang.reflect.Modifier.isPrivate(R13Annotated.getClass.getDeclaredField("serialVersionUID").getModifiers)
    // Scala 2.12 emits a public UID. Keep public fields as payload, even for this annotation.
    val uidPayload = if (privateUid) "" else "{serialVersionUID=Long(7)}"
    assert(r13("annotated", 0) == "tag spinaldb.R13Annotated$:spinaldb.R13Annotated$" + uidPayload)
    // A case class's own field beyond its elements (here a private payload) is keyed (round 14: a case
    // class is read by all its fields).
    val cb = r13("caseBitmap", 0)
    assert(cb.contains("payload=Boolean(false)") && cb.contains("x=Int(0)") && !ExprText.isIncomplete(cb), cb)
    // A constant `final val` has no field: it is keyed from the Scala signature.
    val (c0, c1) = (r13("const", 0), r13("const", 1))
    assert(c0.contains("k=Int(0)") && c1.contains("k=Int(1)") && !ExprText.isIncomplete(c0), s"$c0 $c1")
    val ca = r13("constAttr", 0)
    assert(ca.contains("k=Int(1)") && !ExprText.isIncomplete(ca), ca)
    // The role of each field, from the compiled classes.
    def role(c: Class[_], n: String) = Extractor.fieldRole(c.getDeclaredField(n))
    assert(role(R13Lazy.getClass, "bitmap$0") == Extractor.FieldRole.Compiler)
    assert(role(R13Annotated.getClass, "serialVersionUID") ==
      (if (privateUid) Extractor.FieldRole.Compiler else Extractor.FieldRole.Payload))
    assert(role(R13Lazy.getClass, "MODULE$") == Extractor.FieldRole.Compiler)
    assert(role(classOf[`FalseModule$`], "MODULE$") == Extractor.FieldRole.Payload)
    assert(role(R13Bitmap.getClass, "bitmap$0") == Extractor.FieldRole.Payload)
    assert(role(R13Serial.getClass, "serialVersionUID") == Extractor.FieldRole.Payload)
    assert(role(R13TraitBitmap.getClass, "bitmap$0") == Extractor.FieldRole.Payload)
    assert(role(classOf[R13CaseBitmap], "payload") == Extractor.FieldRole.Payload)
  }

  private def r14(kind: String, mode: Int): String =
    rows(build(s"r14$kind$mode", probe)(new Round14Design(kind, mode)), "SELECT tags FROM signals WHERE path = 'io_y'")
      .map(_.mkString("|")).mkString("\n")

  test("round 14: a case-class tag is keyed by its fields, never through methods it can override") {
    // `productIterator`, `productElement` and `productElementNames` overridden: the fields still count.
    for (k <- Seq("hidden", "element")) {
      val (d0, d1) = (r14(k, 0), r14(k, 1))
      assert(d0 != d1 && !ExprText.isIncomplete(d0) && d0.contains("x=Int(0)") && d1.contains("x=Int(1)"), s"$k: $d0 $d1")
    }
    // A field beyond the elements is read too (it was not modelled).
    val b = r14("body", 1)
    assert(b.contains("x=Int(1)") && b.contains("y=Int(2)") && !ExprText.isIncomplete(b), b)
  }

  test("round 14: user-overridable methods of a tag payload never decide its key") {
    // Same key in both modes only if incomplete: a number class whose `toString` is the user's, a
    // collection that is not the Scala library's, a subclass of a Spinal tag the encoder writes in a
    // short form (`ExternalDriverTag`, `MemSymbolesTag`'s mappings, a `ClockDomain` by its row).
    for (k <- Seq("bigInteger", "bigInt", "bigDecimal", "fakeSeq", "driver", "mapping", "domain")) {
      val (d0, d1) = (r14(k, 0), r14(k, 1))
      assert(d0 != d1 || ExprText.isIncomplete(d0), s"$k: $d0 $d1")
      assert(!d0.contains("tag spinal.core.ExternalDriverTag:"), s"$k: $d0")
    }
    for (k <- Seq("bigInteger", "bigInt", "bigDecimal", "fakeSeq")) assert(ExprText.isIncomplete(r14(k, 0)), k)
    // The clock-enable role tag's `:self` form is only for Spinal's own class.
    val q = "SELECT clock_enable_key FROM clock_domains WHERE clock_enable IS NOT NULL"
    val (e0, e1) = (rows(build("r14en0", probe)(new R14EnableDesign(0)), q), rows(build("r14en1", probe)(new R14EnableDesign(1)), q))
    assert(e0.size == 1 && (e0 != e1 || e0.flatten.exists(ExprText.isIncomplete)), s"$e0 $e1")
    // Spinal's own classes keep their forms.
    val (s1, s2) = (rows(build("r14sym1", probe)(new TagDesign("symbols1")), "SELECT tags FROM signals WHERE path = 'io_y'").head.head,
      rows(build("r14sym2", probe)(new TagDesign("symbols2")), "SELECT tags FROM signals WHERE path = 'io_y'").head.head)
    assert(s1 != s2 && s1.startsWith("tag spinal.core.MemSymbolesTag:[") && !ExprText.isIncomplete(s1), s"$s1 $s2")
  }

  test("allow-list: every Spinal expression class is modelled except a pinned few; statement kinds are pinned") {
    // A reflection sweep over spinalhdl-core: what `ExprText.modelled` accepts is the supported set in
    // SpinalDB/README.md. A Spinal upgrade that adds a node class, a field or a statement kind fails here.
    import scala.collection.JavaConverters._
    val location = Paths.get(classOf[Bool].getProtectionDomain.getCodeSource.getLocation.toURI)
    val names = if (Files.isDirectory(location)) {
      val files = Files.walk(location)
      try files.iterator.asScala.filter(p => Files.isRegularFile(p))
        .map(p => location.relativize(p).toString.replace(File.separatorChar, '/')).toVector
      finally files.close()
    } else {
      val zip = new java.util.zip.ZipFile(location.toFile)
      try zip.entries.asScala.map(_.getName).toVector finally zip.close()
    }
    val classes = names.filter(n => n.startsWith("spinal/core/") && n.endsWith(".class"))
      .map(_.stripSuffix(".class").replace('/', '.'))
      .flatMap(n => scala.util.Try[Class[_]](Class.forName(n, false, this.getClass.getClassLoader)).toOption)
    def concrete(c: Class[_]) = !c.isInterface && !java.lang.reflect.Modifier.isAbstract(c.getModifiers)
    val exprs = classes.filter(c => concrete(c) && classOf[spinal.core.internals.Expression].isAssignableFrom(c) &&
      !classOf[BaseType].isAssignableFrom(c))
    val asyncPort = classOf[SpinalApi.AsyncWritePort]
    if (asyncPort.getSimpleName == "MemReadAsyncWrite") assert(exprs.size > 140, exprs.size)
    else assert(exprs.size == 137, exprs.size)
    val unmodelled = exprs.filterNot(ExprText.modelled).map(_.getName).toSet
    assert(unmodelled.isEmpty, exprs.filterNot(ExprText.modelled).map(c => s"${c.getName}: origin=${LibraryClasses.isSpinal(c)} missing=${ExprText.params(c) -- ExprText.handled(c)}").mkString("; "))
    val statements = classes.filter(c => concrete(c) && classOf[spinal.core.internals.Statement].isAssignableFrom(c) &&
      !classOf[BaseType].isAssignableFrom(c)).map(_.getSimpleName).toSet
    val asyncPorts = if (asyncPort.getSimpleName == "MemReadAsyncWrite") Seq(asyncPort) else Nil
    val expected = Set("Mem", "MemWrite", "MemReadSync", "MemReadAsync", "MemReadWrite",
      "AssertStatement", "DataAssignmentStatement", "InitAssignmentStatement", "InitialAssignmentStatement",
      "SwitchStatement", "WhenStatement") ++ asyncPorts.map(_.getSimpleName)
    assert(statements == expected, statements)
    // Every memory port's fields are written into its key.
    for (c <- Seq(classOf[MemWrite], classOf[MemReadSync], classOf[MemReadAsync], classOf[MemReadWrite]) ++ asyncPorts)
      assert(ExprText.params(c).subsetOf(ExprText.MemPortFields(c)), (c, ExprText.params(c)))
  }

  test("--args-file passes arguments with spaces and semicolons unchanged") {
    val f = Files.createTempFile("spinaldb-args", "")
    Files.write(f, "my.Top\u0000/tmp/a b;c.db\u0000--meta\u0000k=x y; z\u0000".getBytes("UTF-8"))
    val (o, _, pos) = Main.parse(Seq("--args-file", f.toString))
    assert(pos == Seq("my.Top", "/tmp/a b;c.db") && o.meta == Seq("k" -> "x y; z"))
  }
}
