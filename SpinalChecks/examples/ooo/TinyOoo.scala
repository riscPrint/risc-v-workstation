package spinalchecks.examples.ooo

import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinalchecks._
import spinalprobes.Probe

/** Four ROB slots, eight physical tags, two architectural registers.
  * The instruction payload is only a tag and a store byte. */
class TinyOoo(bug: String = "clean") extends Component {
  val io = new Bundle {
    val dispatch, wake, commit, mispredict, load, fence = in Bool()
    val destination = in UInt(1 bits)
    val store = in Bool()
    val data = in Bits(8 bits)
    val retired = out Bool()
    val retiredTag = out UInt(3 bits)
    val forwarded = out Bool()
    val loadData = out Bits(8 bits)
  }
  val count = Reg(UInt(3 bits)).init(0)
  val head = Reg(UInt(2 bits)).init(0).simPublic()
  val tail = Reg(UInt(2 bits)).init(0)
  val free = Reg(Bits(8 bits)).init(0xfc)
  val map = Vec(Reg(UInt(3 bits)).init(0), Reg(UInt(3 bits)).init(1))
  val committed = Vec(Reg(UInt(3 bits)).init(0), Reg(UInt(3 bits)).init(1))
  val valid = Vec.fill(4)(Reg(Bool()).init(False))
  val ready = Vec.fill(4)(Reg(Bool()).init(False))
  val done = Vec.fill(4)(Reg(Bool()).init(False))
  val physical = Vec.fill(4)(Reg(UInt(3 bits)).init(0))
  val previous = Vec.fill(4)(Reg(UInt(3 bits)).init(0))
  val destination = Vec.fill(4)(Reg(UInt(1 bits)).init(0))
  val stores = Vec.fill(4)(Reg(Bool()).init(False))
  val values = Vec.fill(4)(Reg(Bits(8 bits)).init(0))
  val serial = Vec.fill(4)(Reg(UInt(16 bits)).init(0))
  val nextSerial = Reg(UInt(16 bits)).init(0)
  val allocation = UInt(3 bits)
  if(bug == "double_allocate") allocation := map(io.destination)
  else {
    allocation := 0
    for(i <- 7 to 0 by -1) when(free(i)) { allocation := i }
  }
  val fenceActive = RegInit(False)
  val fenceStart = io.fence && !fenceActive
  val fenceDone = fenceActive && count === 0
  when(fenceStart) { fenceActive := True }
  when(fenceDone) { fenceActive := False }
  val push = !fenceActive && !io.fence && io.dispatch && count < 4 && free.orR && !io.mispredict
  val retirementSlot = if(bug == "commit_order") head + 1 else head
  val pop = io.commit && count =/= 0 && done(head) && !io.mispredict
  val selectedIssue = Bits(4 bits)
  selectedIssue := 0
  // Highest ready slot can issue before an older blocked slot.
  for(i <- 0 until 4) when(valid(i) && !done(i) && ready(i)) {
    selectedIssue := B(1 << i, 4 bits)
  }
  if(bug == "not_ready") when(valid(head) && !done(head) && !ready(head)) {
    selectedIssue := (B(1,4 bits) |<< head)
  }
  val flush = io.mispredict
  val committedMask = (B(1,8 bits) |<< committed(0)) | (B(1,8 bits) |<< committed(1))
  val speculativeMask = Bits(8 bits)
  speculativeMask := 0
  for(i <- 0 until 4) when(valid(i)) { speculativeMask(physical(i)) := True }
  val liveMask = committedMask | speculativeMask

  when(push) {
    valid(tail) := True; ready(tail) := False; done(tail) := False
    physical(tail) := allocation; previous(tail) := map(io.destination)
    destination(tail) := io.destination
    stores(tail) := io.store; values(tail) := io.data
    serial(tail) := nextSerial; nextSerial := nextSerial + 1
    map(io.destination) := allocation
    tail := tail + 1
  }
  for(i <- 0 until 4) {
    when(io.wake && valid(i)) { ready(i) := True }
    when(selectedIssue(i)) { done(i) := True }
  }
  when(pop) {
    valid(retirementSlot) := False
    committed(destination(retirementSlot)) := physical(retirementSlot)
    head := head + 1
  }
  when(push || pop) {
    val allocated = Mux(push, B(1,8 bits) |<< allocation, B(0,8 bits))
    val released = Mux(pop, B(1,8 bits) |<< previous(retirementSlot), B(0,8 bits))
    if(bug == "leak") free := free & ~allocated
    else free := (free | released) & ~allocated
  }
  when(push && !pop) { count := count + 1 }
  when(pop && !push) { count := count - 1 }
  when(flush) {
    free := ~committedMask
    for(i <- 0 until 2) {
      if(bug == "stale_map" && i == 0) map(i) := allocation
      else map(i) := committed(i)
    }
    for(i <- 0 until 4) { valid(i) := False; ready(i) := False; done(i) := False }
    head := 0; tail := 0
    if(bug == "lost_flush") count := count else count := 0
  }
  io.retired := pop

  // A load is younger than all entries except the newest dispatch.
  // Its age point is explicitly independent of the forwarding select.
  val loadAge = nextSerial - 1
  val eligible = Bits(4 bits)
  val expectedSelect = Bits(4 bits)
  val selectedForward = Bits(4 bits)
  for(i <- 0 until 4) eligible(i) := valid(i) && stores(i) && serial(i) < loadAge
  expectedSelect := 0
  for(i <- 0 until 4) {
    val youngerEligible = (0 until 4).filter(_ != i).map(j => eligible(j) && serial(j) > serial(i)).reduce(_ || _)
    when(eligible(i) && !youngerEligible) { expectedSelect(i) := True }
  }
  selectedForward := expectedSelect
  if(bug == "young_store") {
    for(i <- 0 until 4) when(valid(i) && stores(i) && serial(i) >= loadAge) {
      selectedForward := B(1 << i,4 bits)
    }
  }

  io.forwarded := selectedForward.orR
  io.loadData := (0 until 4).map(i => Mux(selectedForward(i), values(i), B(0,8 bits))).reduce(_ | _)
  io.retiredTag := physical(retirementSlot)
  val observedToken = io.retiredTag.asBits
  val binding = new java.util.Properties()
  val stream = new java.io.FileInputStream("bindings.properties")
  try binding.load(stream) finally stream.close()
  val named: Map[String, Data] = Map("push" -> push, "pop" -> pop, "flush" -> flush,
    "allocation" -> allocation.asBits, "observedToken" -> observedToken, "count" -> count,
    "free" -> free, "liveMask" -> liveMask, "selectedIssue" -> selectedIssue,
    "ready" -> Cat(ready), "selectedForward" -> selectedForward, "expectedSelect" -> expectedSelect)
  def bound[T <: Data](key: String): T = {
    val signal = binding.getProperty(key)
    require(signal != null && named.contains(signal), "missing fixture binding: " + key)
    named(signal).asInstanceOf[T]
  }
  QueueChecks.fifo("rob",4,bound[Bool]("rob.push"),bound[Bool]("rob.pop"),bound[Bool]("rob.flush"),
    bound[Bits]("rob.pushed"),bound[Bits]("rob.popped"),bound[UInt]("rob.count"))
  QueueChecks.arbiter("issue", Cat((0 until 4).map(i => valid(i) && ready(i) && !done(i))),selectedIssue)
  DeclaredChecks.rule("freelist.conservation","rename","free tags plus current committed and speculative owners", trigger=True)(
    (bound[Bits]("rename.free") & bound[Bits]("rename.live")).orR || (bound[Bits]("rename.free") | bound[Bits]("rename.live")) =/= B(255,8 bits))
  // Each helper is asserted in the same clock domain as conservation.
  DeclaredChecks.rule("rename.occupancy", "rename", "ROB occupancy equals live slots and stays within capacity", trigger=True)(
    count > 4 || count =/= CountOne(Cat(valid)))
  val mapMask = (B(1,8 bits) |<< map(0)) | (B(1,8 bits) |<< map(1))
  DeclaredChecks.rule("rename.disjoint", "rename", "mapped and committed tags are distinct and not free", trigger=True)(
    map(0) === map(1) || committed(0) === committed(1) || (free & (mapMask | committedMask)).orR)
  DeclaredChecks.rule("rename.capacity", "rename", "free tags plus speculative occupancy equals six", trigger=True)(
    CountOne(free).resize(5) + count.resize(5) =/= 6)
  val ownerErrors = (0 until 4).map(i => valid(i) && (
    free(physical(i)) || committedMask(physical(i)) ||
    (0 until 4).filter(_ != i).map(j => valid(j) && physical(i) === physical(j)).reduce(_ || _)))
  DeclaredChecks.rule("rename.owners", "rename", "each speculative physical tag has one owner and is not free", trigger=True)(ownerErrors.reduce(_ || _))
  var expectedMap: Seq[UInt] = committed.toSeq
  val chainErrors = scala.collection.mutable.ArrayBuffer[Bool]()
  chainErrors += (tail =/= head + count.resize(2))
  for(offset <- 0 until 4) {
    val slot = head + U(offset, 2 bits)
    chainErrors += (valid(slot) =/= (count > offset))
    val expectedPrevious = Mux(destination(slot) === 0, expectedMap(0), expectedMap(1))
    chainErrors += (valid(slot) && previous(slot) =/= expectedPrevious)
    expectedMap = (0 until 2).map(r => Mux(valid(slot) && destination(slot) === r, physical(slot), expectedMap(r)))
  }
  chainErrors ++= (0 until 2).map(r => map(r) =/= expectedMap(r))
  DeclaredChecks.rule("rename.chain", "rename", "rename previous-tag chains follow ROB age and end at the map", trigger=True)(chainErrors.reduce(_ || _))
  DeclaredChecks.rule("freelist.allocate","rename","two accepted allocation ports have distinct tags", trigger=push)(
    push && !free(allocation))
  DeclaredChecks.rule("execution.operands","iq","all operands ready before selection", trigger=selectedIssue.orR)(
    (bound[Bits]("iq.selected") & ~bound[Bits]("iq.ready")).orR)
  DeclaredChecks.rule("store.forward_age","sq","select the youngest eligible older store", trigger=io.load)(
    io.load && bound[Bits]("sq.selected") =/= bound[Bits]("sq.expected"))
  val afterFlush = RegNext(flush).init(False)
  DeclaredChecks.rule("recovery.map","rename","flush restores committed architectural names", trigger=afterFlush)(
    afterFlush && (map(0) =/= committed(0) || map(1) =/= committed(1)))
  DeclaredChecks.rule("recovery.flush","rob","flush clears speculative occupancy", trigger=afterFlush)(
    afterFlush && count =/= 0)
  // Per-slot references accept the broadcast wake and multi-slot flush.
  for(i <- 0 until 4) {
    val allocated = push && tail === i
    val retired = pop && retirementSlot === i
    ExecutionChecks.bind("iq_" + i, 1, 1,
      allocated, U(0,1 bits), B(0,1 bits),
      io.wake && valid(i) && !flush, U(0,1 bits), B(1,1 bits),
      selectedIssue(i) && !flush, U(0,1 bits),
      False, U(0,1 bits), retired, U(0,1 bits), flush.asBits)
    RecoveryChecks.bind("rob_" + i, 1,
      allocated, U(0,1 bits), nextSerial,
      retired || (flush && valid(i)), U(0,1 bits), serial(i),
      retired, U(0,1 bits), serial(i),
      False, U(0,1 bits), serial(i),
      flush.asBits, fenceStart, fenceDone, valid(i).asBits)
  }
  Probe.stage("Rn", push, nextSerial)
  for(i <- 0 until 4) {
    Probe.stageAt("issue_" + i, "Is", selectedIssue(i) && !flush, serial(i))
    Probe.flush("kill_" + i, flush && valid(i), serial(i))
  }
  Probe.retire("Cm", pop, serial(retirementSlot))
  // The fixture command denotes addi x(destination+1), x0, data.
  val retiredSerial = out(serial(retirementSlot)).setName("retiredSerial")
  val retiredDestination = out(destination(retirementSlot)).setName("retiredDestination")
  val retiredValue = out(values(retirementSlot)).setName("retiredValue")
  Probe.counter("rename_occupancy",CountOne(speculativeMask))
  Probe.counter("rob_occupancy",count)
  Probe.counter("iq_occupancy",CountOne(Cat((0 until 4).map(i => valid(i) && !done(i)))))
  Probe.flush("mispredict",flush,nextSerial)
  Probe.faultSite("rob_head",head)
}
