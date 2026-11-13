package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.misc.SizeMapping
import spinal.lib.bus.tilelink._
import spinal.lib.bus.tilelink.coherent.CacheFiber
import spinal.lib.bus.tilelink.fabric.{MasterBus, SlaveBus}
import spinal.lib.bus.tilelink.fabric.sim.TilelinkTester
import spinal.lib.bus.tilelink.sim._
import spinal.lib.system.tag.PMA

/** Exercise the library's real writeback cache, rather than fixture permissions. */
class CoherentCacheNativeSpec extends AnyFunSuite {
  class Top extends Component {
    val masters = new MasterBus(M2sParameters(addressWidth=32, dataWidth=64,
      masters=List.tabulate(2)(i => M2sAgent(name=null, mapping=List(M2sSource(
        id=SizeMapping(i*4,4), emits=M2sTransfers(acquireT=SizeRange(64), acquireB=SizeRange(64),
          get=SizeRange(1,64), putFull=SizeRange(1,64), putPartial=SizeRange(1,64))))))))
    val cache = new CacheFiber()
    cache.parameter.cacheWays = 1
    cache.parameter.cacheBytes = 1024
    cache.up << masters.node
    val ram = new SlaveBus(M2sSupport(transfers=M2sTransfers.all, dataWidth=64, addressWidth=12), S2mParameters.none())
    ram.node at 0x10000 of cache.down
    ram.node.addTag(PMA.MAIN)
  }

  private def run(corrupt: Boolean): Unit = {
    val work = Files.createTempDirectory("coherent-cache-native").toFile
    try {
      val tester = new TilelinkTester(new Top, SimConfig.withVerilator.workspacePath(work.getPath))
      tester.doSim("coherent-data") { tb =>
        val expected = new MemoryImage(4096)
        tb.nodeToModel.values.foreach(_.write(0, Array.fill[Byte](4096)(0)))
        tb.slavesStuff.foreach(_.model.mem.write(0, Array.fill[Byte](4096)(0)))
        if (corrupt) tb.slavesStuff.head.model.mem.write(63,Array[Byte](1))
        val agent = tb.mastersStuff.head.agent
        val cd = agent.cd
        // Establish a fixed clock coordinate before issuing any client traffic.
        cd.waitSampling(); val clockOrigin = simTime()
        cd.waitSampling(); val clockPeriod = simTime()-clockOrigin
        require(clockPeriod > 2)
        def cycle(): Long = (simTime()-clockOrigin)/clockPeriod
        val progress = new TileLinkProgressObserver(2048, 32,
          "seeded finite client service; B/D ready gaps checked separately at 256 cycles", () => cycle())
        tb.mastersStuff.head.monitor.add(progress)
        val environment = new FairnessMonitor(Set("B", "D"), 256, 1)
        val permissions = new CoherenceMonitor(64, Set(0,1))
        var interventions = 0; var releases = 0; var writebacks = 0
        var stalls = 0; var outstanding = Set.empty[Int]; var racing = false
        def local(a: BigInt): Int = (a - 0x10000).toInt
        def cap(p: Int): String = Seq("T","B","N")(p)
        tb.mastersStuff.head.monitor.subscribers.prepend(new MonitorSubscriber {
          override def onA(a: TransactionA): Unit = {
            outstanding += a.source
            if (outstanding.size >= 2) racing = true
          }
          override def onD(d: TransactionD): Unit = {
            if (d.withData) assert(d.data.toVector == expected.read(local(d.address),d.bytes), "cache response byte mismatch")
            if (d.opcode == Opcode.D.GRANT || d.opcode == Opcode.D.GRANT_DATA)
              permissions.grant(d.source/4, local(d.address),cap(d.param))
            if (d.opcode != Opcode.D.RELEASE_ACK) outstanding -= d.source
          }
          override def onC(c: TransactionC): Unit = {
            val (from,to) = Param.reportPruneFromTo(c.param)
            if (c.withData) assert(c.data.toVector == expected.read(local(c.address),c.bytes), "dirty transfer byte mismatch")
            if (from != to) permissions.shrink(c.source/4,local(c.address),cap(from),cap(to),c.withData,c.withData)
            if (c.opcode == Opcode.C.PROBE_ACK_DATA) interventions += 1
            if (c.opcode == Opcode.C.RELEASE || c.opcode == Opcode.C.RELEASE_DATA) releases += 1
          }
        })
        tb.slavesStuff.head.model.monitor.add(new MonitorSubscriber {
          override def onA(a: TransactionA): Unit = {
            if (a.withData) {
              assert(a.data.toVector == expected.read(a.address.toInt,a.bytes), "writeback byte mismatch")
              writebacks += 1
            }
          }
        })
        val bus = tester.c.report.toplevel.asInstanceOf[Top].masters.node.bus
        cd.onSamplings {
          val offered = Set("B", "D").filter {
            case "B" => bus.b.valid.toBoolean
            case _ => bus.d.valid.toBoolean
          }
          val enabled = Set("B", "D").filter {
            case "B" => bus.b.ready.toBoolean
            case _ => bus.d.ready.toBoolean
          }
          environment.sample(cycle(), offered, enabled, offered intersect enabled)
          // Run after all accepted-message callbacks at this edge.
          fork { sleep(1); progress.tick() }
          if ((bus.a.valid.toBoolean && !bus.a.ready.toBoolean) ||
              (bus.c.valid.toBoolean && !bus.c.ready.toBoolean) ||
              (bus.d.valid.toBoolean && !bus.d.ready.toBoolean)) stalls += 1
        }
        agent.driver.driver.randomizeStallRate()
        tb.slavesStuff.foreach(_.model.driver.driver.randomizeStallRate())
        def word(value: Int) = (0 until 4).map(i => (value >>> (8*i)).toByte)
        expected.write(0,word(37),15)
        agent.putFullData(0,0x10000,word(37))
        val owner = agent.acquireBlock(0,Param.Grow.NtoT,0x10000,64)
        assert(owner.data.toVector == expected.read(0,64))
        // Independent stimulus dirties a simulated coherent client. The DUT cache
        // must obtain these bytes through real B/C handshakes before granting B.
        expected.write(0,word(85),15)
        word(85).zipWithIndex.foreach { case (b,i) => owner.data(i) = b }
        owner.dirty = true
        val reader = agent.acquireBlock(4,Param.Grow.NtoB,0x10000,64)
        assert(reader.data.toVector == expected.read(0,64))
        agent.block.blocks.values.toList.filter(_.address == 0x10000).foreach { b =>
          if (b.cap != Param.Cap.toN) agent.releaseAuto(b.source,Param.Cap.toN,b)
        }
        // Hold D acceptance while presenting both A requests. This creates an
        // observed overlap instead of relying on a random stall to do so.
        agent.driver.driver.a.ctrl.setFactor(1.0f)
        agent.driver.driver.d.factor = 0.0f
        val first = fork { agent.acquireBlock(0,Param.Grow.NtoT,0x10040,64) }
        val second = fork { agent.acquireBlock(4,Param.Grow.NtoT,0x10040,64) }
        cd.waitSampling(80)
        assert(racing, s"both racing A requests must be accepted before D release: $outstanding")
        agent.driver.driver.d.factor = 0.5f
        first.join(); second.join()
        assert(tb.slavesStuff.head.model.mem.readBytes(0,64).toVector != expected.read(0,64),
          "test needs dirty cache data that has not reached backing memory")
        val beforeEviction = writebacks
        // Same-set alias forces actual cache replacement and dirty writeback.
        expected.write(1024,word(99),15)
        agent.putFullData(0,0x10400,word(99))
        assert(writebacks > beforeEviction, "same-set replacement did not write back dirty data")
        assert(agent.get(0,0x10000,4).data.toVector == word(85).toVector)
        cd.waitSampling(40)
        assert(tb.slavesStuff.head.model.mem.readBytes(0,64).toVector == expected.read(0,64), "backing memory after eviction")
        assert(interventions > 0 && releases > 0 && writebacks > 0, "required coherence transitions not observed")
        assert(stalls > 0 && racing, "backpressure or overlapping requests not observed")
        tb.waitCheckers()
        cd.waitSampling(); sleep(2)
        progress.finish(Set("a", "b", "c_probe_ack", "c_release_complete", "d_grant", "d_release_ack", "e"))
        environment.finish(Set("B", "D"))
        info(s"accepted TL-C progress: ${progress.coverage}; max B/D ready gap=${environment.maxDisabled}")
      }
      // TilelinkTester accumulates exceptions. Never infer success from doSim alone.
      if (corrupt) assert(tester.errors.toString.contains("cache response byte mismatch"), tester.errors.toString)
      tester.checkErrors()
    } finally org.apache.commons.io.FileUtils.deleteDirectory(work)
  }
  test("real cache intervention, racing grants and dirty eviction with accepted-channel byte checks") {
    run(false)
  }
  test("fault: corrupt backing byte cannot pass the independent cache observer") {
    val e = intercept[Exception](run(true))
    assert(e.getMessage.contains("Some tests failed"))
  }

}
