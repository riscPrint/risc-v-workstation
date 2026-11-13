package rvwsmp
import java.io.File
import spinal.core._
import spinal.core.fiber.Fiber
import spinal.core.sim._
import spinal.lib.bus.tilelink
import spinal.lib.bus.tilelink.fabric.Node
import spinal.lib.bus.tilelink.coherent.HubFiber
import spinal.lib.bus.tilelink.sim._
import spinal.lib.misc.TilelinkClintFiber
import spinal.lib.misc.plic.TilelinkPlicFiber
import vexiiriscv.ParamSimple
import vexiiriscv.soc.TilelinkVexiiRiscvFiber
import vexiiriscv.test.VexiiRiscvProbe
import riscvsim._

/** Real cached cores and coherent hub, separate from cacheless C1. */
class SnapshotPlugins(initial: Seq[spinal.lib.misc.plugin.Hostable])
    extends scala.collection.mutable.ArrayBuffer[spinal.lib.misc.plugin.Hostable] {
  this ++= initial
  override def foreach[U](f: spinal.lib.misc.plugin.Hostable => U): Unit = iterator.toVector.foreach(f)
}
class CachedSmpTop(image: File) extends Component {
  val expected_data = in Bits(512 bits)
  val param = new ParamSimple
  param.xlen = 64; param.addISA("m", "a")
  param.fetchL1Enable = true; param.lsuL1Enable = true
  param.lsuL1Coherency = true; param.resetVector = 0x80000000L
  param.fixIsaParams()
  val cores = (0 until 2).map(h => new TilelinkVexiiRiscvFiber(new SnapshotPlugins(param.plugins(h).toVector)))
  val cached = Node()
  cores.foreach(c => cached << List(c.iBus, c.lsuL1Bus))
  val hub = new HubFiber; hub.up << cached
  val ramBus = Node(); ramBus << hub.down
  val ram = new tilelink.fabric.RamFiber(64*1024)
  ram.up at 0x80000000L of ramBus
  val dataRam = new tilelink.fabric.RamFiber(4096)
  dataRam.up at 0x80080000L of ramBus
  val ioBus = Node(); cores.foreach(c => ioBus << c.dBus)
  val clint = new TilelinkClintFiber; clint.node at 0x2000000L of ioBus
  val plic = new TilelinkPlicFiber; plic.node at 0xc000000L of ioBus
  val external = spinal.lib.misc.InterruptNode.master()
  external.flag := False
  plic.mapUpInterrupt(1, external)
  cores.foreach { c => c.bind(clint); c.bind(plic) }
  val taps = Fiber patch new Area {
    val source = new ElfFile(image)
    Seq((ram,0x80000000L),(dataRam,0x80080000L)).foreach { case (region,base) =>
      val mem = region.thread.logic.mem
      val bytes = mem.wordType.getBitsWidth/8
      val words = Array.fill[BigInt](mem.wordCount)(0)
      source.load { (address,data) => data.indices.foreach { i =>
        val offset=address+i-base
        if(offset >= 0 && offset < mem.wordCount.toLong*bytes) {
          val index=(offset/bytes).toInt; val shift=(offset%bytes).toInt*8
          words(index) = (words(index) & ~((BigInt(255))<<shift)) | (BigInt(data(i)&255)<<shift)
        }
      } }
      mem.initBigInt(words.toSeq)
    }
    val buses = cores.map(_.lsuL1Bus.bus)
    buses.foreach(_.flatten.foreach(_.simPublic()))
    val selected = buses.zipWithIndex.map { case (bus,h) => CachedLineTap(bus).setName(s"observed$h") }
    selected.foreach(bus => out(bus))
    val sampled = selected.flatMap(_.flatten).map(signal => signal -> signal.asBits.simPublic())
  }
}
object CachedSmpMain {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "ELF and output directory required")
    val elf = new ElfFile(new File(args(0)))
    val out = new File(args(1)); out.mkdirs()
    val compiled = SimConfig.withVerilator.withConfig(SpinalConfig(inlineRom=true))
      .cachePath(new File(out.getParentFile,"native-cache").getPath)
      .workspacePath(new File(out,"sim").getPath).compile(new CachedSmpTop(elf.file))
    var grants = 0; var shrinks = 0
    compiled.doSim("cached-smp", 17) { dut =>
      val cd = dut.clockDomain
      val permissions = new CoherenceMonitor(64, Set(0,1))
      val data = new CachedDataObserver
      dut.expected_data #= 0
      val retired = Array.fill(2)(0L)
      val done = scala.collection.mutable.Set.empty[Int]
      var cycle = 0L
      val accepted = scala.collection.mutable.ArrayBuffer.empty[(Int,()=>Unit)]
      def local(a: BigInt) = (a-BigInt("80000000",16)).toInt
      def cap(p: Int) = Seq("T","B","N")(p)
      dut.taps.buses.zipWithIndex.foreach { case (bus,h) =>
        new Monitor(bus,cd).add(new MonitorSubscriber {
          override def onD(d: TransactionD): Unit = {
            if(d.opcode == tilelink.Opcode.D.GRANT || d.opcode == tilelink.Opcode.D.GRANT_DATA) {
              accepted += ((1,()=>{
                permissions.grant(h,local(d.address),cap(d.param)); grants += 1
                if(d.withData && d.address == data.address) data.refill(h,cycle,d.data.toVector)
              }))
            }
          }
          override def onC(c: TransactionC): Unit = {
            val (from,to) = tilelink.Param.reportPruneFromTo(c.param)
            accepted += ((0,()=>{
            if(c.address == data.address) {
              if(c.withData) data.event("writeback",h,cycle,c.data.toVector)
              if(to == tilelink.Param.Cap.toN && from != to) data.event("invalidate",h,cycle)
            }
            if(from != to) { permissions.shrink(h,local(c.address),cap(from),cap(to),from == tilelink.Param.Cap.toT && c.withData,c.withData); shrinks += 1 }
            }))
          }
        })
      }
      dut.cores.zipWithIndex.foreach { case (fiber,h) =>
        val backend = new C2Backend(64,()=>cycle,()=>3,
          ()=>throw new IllegalStateException("unexpected cached trap"), _=>(),
          (_,_,_,_)=>throw new IllegalStateException("unexpected cached trap"),
          (address,size,data)=> {
            val host = BigInt(elf.symbol("tohost").get)+h*8
            if(address == host) { require(data == 1,"cached program failed"); done += h }
          }, r => { retired(h) += 1; data.retire(h,r); dut.expected_data #= data.expected })
        val probe = new VexiiRiscvProbe(fiber.logic.core,None,withRvls=false)
        probe.checkLiveness=false; probe.trace=false; probe.add(backend)
      }
      val capture = new java.io.PrintWriter(new File(out,"projected.jsonl"))
      def sample(): Unit = {
        val row = ujson.Obj("clk"->(if(cd.clockSim.toBoolean) "0x1" else "0x0"), "reset"->(if(cd.isResetAsserted) "0x1" else "0x0"),
          "expected_data"->("0x"+dut.expected_data.toBigInt.toString(16)))
        dut.taps.sampled.foreach { case (signal,bits) => row(signal.getName())="0x"+bits.toBigInt.toString(16) }
        capture.println(ujson.write(row))
      }
      cd.onActiveEdges { sample() }
      forkSensitive(cd.resetSim) { sample() }
      cd.onSamplings { fork { sleep(1)
        val batch = accepted.sortBy(_._1).toVector; accepted.clear()
        batch.foreach(_._2())
      } }
      cd.forkStimulus(10)
      while(done.size != 2 && cycle < 100000) { cd.waitSampling(); cycle += 1 }
      require(done.size == 2,"cached SMP timeout")
      require(grants > 0 && shrinks > 0,"no coherent handoff observed")
      sleep(2)
      capture.close()
      data.finish()
      val result = ujson.Obj("schema"->"rvw.cached-smp/1","status"->"pass","harts"->2,"seed"->17,
        "lsu_sets"->dut.param.lsuL1Sets,"lsu_ways"->dut.param.lsuL1Ways,
        "cycles"->cycle,"grants"->grants,"shrinks"->shrinks,
        "retirements"->ujson.Arr.from(retired.toSeq),"cache_events"->data.coverage,
        "scope"->"RTL cached cores and coherent hub; permission observer; independent bytes on the selected handoff line")
      java.nio.file.Files.writeString(new File(out,"result.json").toPath,ujson.write(result,indent=2)+"\n")
    }
  }
}
