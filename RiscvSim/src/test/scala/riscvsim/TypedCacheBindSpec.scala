package riscvsim

import java.io.File
import java.nio.file.Files
import java.sql.DriverManager
import org.scalatest.funsuite.AnyFunSuite
import org.scalatest.BeforeAndAfterAll
import scala.collection.mutable.ArrayBuffer
import scala.sys.process._
import spinal.core._
import spinal.core.sim._
import spinal.core.fiber.Fiber
import spinal.lib._
import spinal.lib.bus.misc.SizeMapping
import spinal.lib.bus.tilelink._
import spinal.lib.bus.tilelink.coherent.CacheFiber
import spinal.lib.bus.tilelink.fabric.{MasterBus, SlaveBus, Node}
import spinal.lib.bus.tilelink.fabric.sim._
import spinal.lib.bus.tilelink.sim._
import spinal.lib.system.tag.PMA
import spinaldb.{SpinalDB, DbOptions}

/** Real Spinal Bus types -> C6 -> generated bind -> real CacheFiber traffic. */
class TypedCacheBindSpec extends AnyFunSuite with BeforeAndAfterAll {
  private val preserved = sys.env.get("RVW_TYPED_TLC_OUT")
  private val work = preserved.map(new File(_)).getOrElse(Files.createTempDirectory("typed-cache-bind").toFile)
  require(!work.exists() || Option(work.list()).forall(_.isEmpty), "typed bind output must be fresh")
  work.mkdirs()
  override def afterAll(): Unit = if (preserved.isEmpty) org.apache.commons.io.FileUtils.deleteDirectory(work)

  class TypedCacheTop extends Component {
    val io = new Bundle { val expected_data = in Bits(512 bits); val expected_echo = out Bits(512 bits) }
    io.expected_echo := io.expected_data
    val clockSignal = clockDomain.readClockWire
    val resetSignal = clockDomain.readResetWire
    val masters = Seq.fill(2)(new MasterBus(M2sParameters(addressWidth=32, dataWidth=64,
      masters=List(M2sAgent(name=null, mapping=List(M2sSource(id=SizeMapping(0,4),
        emits=M2sTransfers(acquireT=SizeRange(64), acquireB=SizeRange(64), get=SizeRange(1,64),
          putFull=SizeRange(1,64), putPartial=SizeRange(1,64)))))))))
    val cache = new CacheFiber()
    cache.parameter.cacheWays=1; cache.parameter.cacheBytes=1024
    masters.foreach(m => cache.up << m.node)
    val ram = new SlaveBus(M2sSupport(transfers=M2sTransfers.all, dataWidth=64, addressWidth=12), S2mParameters.none())
    ram.node at 0x10000 of cache.down
    ram.node.addTag(PMA.MAIN)
    Fiber build {
      masters.zipWithIndex.foreach { case (m, i) =>
        m.node.bus.get.setName(s"client${i}_bus")
        m.node.bus.get.simPublic()
      }
    }
  }

  test("generated model projection binds to real typed cache channels") {
    DebugId.setup(16)
    val cfg = SpinalConfig(targetDirectory=new File(work,"rtl").getPath,
      headerWithRepoHash=false, headerWithDate=false, noAssertAtTimeZero=true).includeSimulation
    cfg.addTransformationPhase(new SimVerilatorPhase)
    val report = SpinalDB.elaborate(cfg, traceNaming=false)(new TypedCacheTop)
    val database = new File(work,"design.sqlite")
    SpinalDB.write(report, database, DbOptions(pdg=false, blocks=false, hgldd=false))
    val top = report.toplevel
    val buses = top.masters.map(_.node.bus.get)
    Class.forName("org.sqlite.JDBC")
    val db = DriverManager.getConnection("jdbc:sqlite:"+database.getAbsolutePath)
    val profile = try {
      val root = db.createStatement().executeQuery("SELECT id FROM components WHERE parent_id IS NULL")
      assert(root.next()); val component=root.getInt(1); root.close()
      def signal(data: BaseType): (Int, String) = {
        val query=db.prepareStatement("SELECT id, spinal_path FROM signals WHERE component_id=? AND name=? AND pruned=0")
        query.setInt(1,component); query.setString(2,data.getName())
        val row=query.executeQuery(); assert(row.next(),s"missing emitted signal ${data.getName()}")
        val result=row.getInt(1) -> row.getString(2); assert(!row.next()); row.close(); query.close(); result
      }
      def client(bus: Bus): ujson.Obj = {
        val path=signal(bus.a.valid)._2.stripSuffix(".a.valid")
        val query=db.prepareStatement("SELECT id FROM bundles WHERE component_id=? AND path=? AND class_name IN ('Bus','spinal.lib.bus.tilelink.Bus')")
        query.setInt(1,component); query.setString(2,path)
        val row=query.executeQuery(); assert(row.next(),s"missing typed TileLink Bus at $path")
        val bundle=row.getInt(1); assert(!row.next()); row.close(); query.close()
        val fields=Seq[(String,BaseType)](
          "a_valid"->bus.a.valid,"a_ready"->bus.a.ready,"a_opcode"->bus.a.payload.opcode,
          "a_param"->bus.a.payload.param,"a_source"->bus.a.payload.source,"a_address"->bus.a.payload.address,"a_size"->bus.a.payload.size,
          "b_valid"->bus.b.valid,"b_ready"->bus.b.ready,"b_opcode"->bus.b.payload.opcode,
          "b_param"->bus.b.payload.param,"b_source"->bus.b.payload.source,"b_address"->bus.b.payload.address,"b_size"->bus.b.payload.size,
          "c_valid"->bus.c.valid,"c_ready"->bus.c.ready,"c_opcode"->bus.c.payload.opcode,
          "c_param"->bus.c.payload.param,"c_source"->bus.c.payload.source,"c_address"->bus.c.payload.address,"c_size"->bus.c.payload.size,
          "c_data"->bus.c.payload.data,"c_corrupt"->bus.c.payload.corrupt,
          "d_valid"->bus.d.valid,"d_ready"->bus.d.ready,"d_opcode"->bus.d.payload.opcode,
          "d_param"->bus.d.payload.param,"d_source"->bus.d.payload.source,"d_sink"->bus.d.payload.sink,"d_size"->bus.d.payload.size,
          "d_data"->bus.d.payload.data,"d_denied"->bus.d.payload.denied,"d_corrupt"->bus.d.payload.corrupt,
          "e_valid"->bus.e.valid,"e_ready"->bus.e.ready,"e_sink"->bus.e.payload.sink)
        ujson.Obj("bundle_id"->bundle,"signals"->ujson.Obj.from(fields.map { case (name,data) => name -> ujson.Num(signal(data)._1) }))
      }
      ujson.Obj("schema"->"rvw.tlc-bind/1","bus_family"->"spinal-tilelink","fairness"->"bounded seeded client and memory service",
        "oracle_kind"->"independent-stimulus","source_bits"->buses.head.a.payload.source.getBitsWidth,
        "sink_bits"->buses.head.e.payload.sink.getBitsWidth,"address_bits"->32,"data_bits"->64,
        "size_bits"->buses.head.a.payload.size.getBitsWidth,"line_bytes"->64,"line_address"->"0x10000",
        "bound_cycles"->512,"trunk_dirty"->false,"clock"->signal(top.clockSignal)._1,
        "reset"->signal(top.resetSignal)._1,"expected_data"->signal(top.io.expected_data)._1,
        "clients"->ujson.Arr.from(buses.map(client)))
    } finally db.close()
    val input=new File(work,"profile.json"); Files.writeString(input.toPath,ujson.write(profile,indent=2))
    val tools=new File(sys.props("riscvsim.tools"))
    val command=Seq(new File(tools,"rvw/.venv/bin/python").getPath,"-m","rvw","memory","tilelink-bind",
      "--database",database.getPath,"--profile",input.getPath,"--out",new File(work,"monitor").getPath)
    val generated=ujson.read(Process(command,tools).!!)
    assert(generated("status").str=="generated" && !generated("executed").bool)
    assert(generated("permission_model")("scope").str.contains("permission projection only"))
    report.blackboxesSourcesPaths += generated("monitor").str
    report.blackboxesSourcesPaths += generated("bind").str
    val compiled=SimConfig.withVerilator.workspacePath(new File(work,"sim").getPath).compile(report)
    val nodes=ArrayBuffer[Node](); val orderings=ArrayBuffer[OrderingTag]()
    report.toplevel.walkComponents(_.foreachTag {
      case n: Node if !TileLinkSdkCompat.excluded(n) => nodes += n
      case o: OrderingTag => orderings += o
      case _ =>
    })
    compiled.doSim(seed=42) { dut =>
      implicit val ids: IdAllocator = new IdAllocator(DebugId.width)
      implicit val callback: IdCallback = new IdCallback
      for(i <- 0 until DebugId.space.reserved) ids.allocate(i)
      val tb=TileLinkSdkCompat.testbench(nodes.toSeq,orderings.toSeq,dut)
      nodes.map(_.clockDomain).distinct.foreach(_.forkStimulus(10))
      dut.io.expected_data #= 0
      tb.nodeToModel.values.foreach(_.write(0,Array.fill[Byte](4096)(0)))
      tb.slavesStuff.foreach(_.model.mem.write(0,Array.fill[Byte](4096)(0)))
      val corrupt=sys.env.get("RVW_TYPED_TLC_CORRUPT").contains("1")
      if(corrupt) {
        tb.slavesStuff.head.model.mem.write(63,Array[Byte](1))
        // Isolate the generated RTL checker. The library checker accepts this byte;
        // the independent expected_data signal still requires the original zero.
        tb.nodeToModel.values.foreach(_.write(63,Array[Byte](1)))
      }
      def stuff(i: Int) = {
        val index=tb.masterNodes.indexOf(dut.masters(i).node); assert(index>=0); tb.mastersStuff(index)
      }
      val clients=(0 until 2).map(stuff)
      val cd=clients.head.agent.cd
      var cycles=0; var stalls=0; var accepted=Set.empty[Int]; var probes=0; var grants=0; var acknowledgments=0
      clients.zipWithIndex.foreach { case (s,i) =>
        s.agent.driver.driver.randomizeStallRate()
        s.monitor.add(new MonitorSubscriber {
          override def onA(a: TransactionA): Unit = { accepted += i }
          override def onB(b: TransactionB): Unit = { probes += 1 }
          override def onD(d: TransactionD): Unit = if(d.opcode==Opcode.D.GRANT_DATA) grants += 1
          override def onE(e: TransactionE): Unit = { acknowledgments += 1 }
        })
      }
      tb.slavesStuff.foreach(_.model.driver.driver.randomizeStallRate())
      cd.onSamplings {
        cycles += 1; assert(cycles<3000,"typed cache bind smoke watchdog")
        for(bus <- buses) if((bus.c.valid.toBoolean && !bus.c.ready.toBoolean) || (bus.d.valid.toBoolean && !bus.d.ready.toBoolean)) stalls += 1
      }
      val owner=clients(0).agent.acquireBlock(0,Param.Grow.NtoT,0x10000,64)
      if(corrupt) {
        cd.waitSampling(4)
        fail("generated monitor did not reject the changed backing-memory byte")
      }
      assert(owner.data.forall(_==0))
      owner.data(0)=85.toByte; owner.dirty=true
      dut.io.expected_data #= 85
      val reader=clients(1).agent.acquireBlock(0,Param.Grow.NtoB,0x10000,64)
      assert(reader.data.toVector == Vector(85.toByte) ++ Vector.fill[Byte](63)(0))
      def releaseAll(): Unit = clients.foreach { s =>
        s.agent.block.blocks.values.toList.foreach { b => if(b.cap!=Param.Cap.toN) s.agent.releaseAuto(b.source,Param.Cap.toN,b) }
      }
      releaseAll()
      accepted=Set.empty[Int]
      clients.foreach { s => s.agent.driver.driver.a.ctrl.setFactor(1.0f); s.agent.driver.driver.d.factor=0.0f }
      val first=fork { clients(0).agent.acquireBlock(0,Param.Grow.NtoT,0x10000,64) }
      val second=fork { clients(1).agent.acquireBlock(0,Param.Grow.NtoT,0x10000,64) }
      cd.waitSampling(40); assert(accepted==Set(0,1),"both racing requests must be accepted")
      clients.foreach(_.agent.driver.driver.d.factor=0.5f)
      first.join(); second.join(); releaseAll()
      tb.waitCheckers(); cd.waitSampling(544)
      assert(probes>=2 && grants==4 && acknowledgments==4 && stalls>0,"required real channel observations")
      info(s"typed C6 bind: probes=$probes, grants=$grants, GrantAcks=$acknowledgments, stalled cycles=$stalls")
    }
    info(s"typed design database and monitor artifacts: ${work.getAbsolutePath}")
  }
}
