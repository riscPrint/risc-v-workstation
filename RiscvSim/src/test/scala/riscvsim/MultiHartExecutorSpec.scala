package riscvsim

import java.io.File
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class MultiHartExecutorSpec extends AnyFunSuite {
  private def record(order: Int, cycle: Long): RvfiRecord =
    RvfiRecord(order,cycle,0x13,false,false,false,3,2,0,0,0,0,0,0,order*4,order*4+4,0,0,0,0,0,false)
  def context(root: File, images: HartImages, maxCycles: Long = 8, wall: WallClock = WallClock.none): RunContext = new RunContext {
    val elf = images.harts.head._2
    val job = RunJob(elf.file,root,"fixture",7,false,maxCycles,None,true,false,false,None,None,false,false)
    override val hartImages = Some(images)
    val rvfiHeader = ujson.Obj("core"->"executor-fixture","config"->"three","elf"->elf.file.getPath,"xlen"->64,"isa"->"rv64i")
    def log(line: String): Unit = ()
    def assertIndex: AssertIndex = null
    def outputMark: Long = 0
    override val wallClock = wall
  }
  private def inputs() = {
    val e = new ElfFile(new BootImageSpec().image())
    new HartImages(Seq(2->e,4->e,9->e),64)
  }
  private def runCase(limit: Long = 8, failed: Boolean = false, wall: WallClock = WallClock.none): (RunOutcome,Seq[ujson.Value]) = {
    val root=Files.createTempDirectory("multi-hart-executor").toFile
    val images=inputs(); val ids=Seq(2,4,9)
    val held=scala.collection.mutable.Set.empty[Int]
    val booted=scala.collection.mutable.Map.empty[Int,Long]
    val released=scala.collection.mutable.Set.empty[Int]
    val parked=scala.collection.mutable.Set.empty[Int]
    val counts=scala.collection.mutable.Map(ids.map(_->0): _*)
    var writes=0; var sharedLoaded=false
    val probes=ids.zipWithIndex.map { case (h,i) => h -> new RvfiProbe(Nil) {
      override def sample(cycle: Long): Seq[RvfiRecord] = {
        assert(released(h) && !parked(h))
        if(counts(h)<i+1) { val r=record(counts(h),cycle); counts(h)+=1; Seq(r) } else Nil
      }
    }}.toMap
    val backend=new MultiHartBackend {
      def holdReset(h: Int): Unit = { held += h }
      def writeMemory(a: Long,d: Array[Byte]): Unit = {
        assert(held==ids.toSet && released.isEmpty); writes+=1
        if(a==0x100 && d.headOption.contains(42.toByte)) sharedLoaded=true
      }
      def boot(h: Int,entry: Long): Unit = { assert(sharedLoaded); booted(h)=entry }
      def release(h: Int): Unit = { assert(booted.keySet==ids.toSet); released += h }
      def step(cycle: Long): Unit = { assert(released==ids.toSet) }
      def completion(h: Int): Option[Status] = if(counts(h)==ids.indexOf(h)+1)
        Some(if(failed && h==4) Status.Fail else Status.Pass) else None
      def park(h: Int): Unit = { assert(!parked(h)); parked += h }
    }
    try {
      val outcome=MultiHartExecutor.run(context(root,images,limit,wall),probes,backend)
      assert(writes==2 && parked==ids.toSet)
      val lines=Files.readString(new File(root,"rvfi.jsonl").toPath).linesIterator.map(ujson.read(_)).toSeq
      outcome -> lines
    } finally org.apache.commons.io.FileUtils.deleteDirectory(root)
  }
  test("N harts load shared bytes before release and complete with independent RVFI order") {
    val (out,lines)=runCase()
    assert(out.status==Status.Pass && out.instret==6 && out.cycles==3)
    val records=lines.tail.filter(!_.obj.contains("event"))
    assert(records.map(_("hart").num.toInt)==Seq(2,4,9,4,9,9))
    assert(records.map(_("order").str)==Seq("0","0","0","1","1","2"))
    assert(lines.tail.filter(_.obj.get("event").contains(ujson.Str("hart_end"))).size==3)
  }
  test("a failed hart stays failed after other harts pass") {
    assert(runCase(failed=true)._1.status==Status.Fail)
  }
  test("cycle timeout records the unfinished hart and parks every hart") {
    val (out,lines)=runCase(limit=2)
    assert(out.status==Status.Timeout && out.instret==5)
    val ends=lines.tail.filter(_.obj.get("event").contains(ujson.Str("hart_end")))
    assert(ends.find(_("hart").num==9).get("status").str=="timeout")
  }
  test("wall timeout cannot become an all-hart pass") {
    val (out,_)=runCase(wall=new WallClock(Some(0)))
    assert(out.status==Status.Timeout && out.instret==0 && out.details("wall_clock_timeout").bool)
  }
  test("completion after the wall deadline remains timeout") {
    val wall=new WallClock(None) {
      private var checks=0
      override def over(graceS: Double = 0): Boolean = { checks+=1; checks>1 }
    }
    val (out,lines)=runCase(wall=wall)
    assert(out.status==Status.Timeout && out.details("wall_clock_timeout").bool)
    val ends=lines.tail.filter(_.obj.get("event").contains(ujson.Str("hart_end")))
    assert(ends.forall(_("status").str=="timeout"))
  }
  test("a driver timeout flag stops the run before another step") {
    val wall=new WallClock(None); wall.expired=true
    val (out,_)=runCase(wall=wall)
    assert(out.status==Status.Timeout && out.instret==0)
  }
  test("missing probes fail before loading or releasing harts") {
    val root=Files.createTempDirectory("multi-hart-executor-missing").toFile
    val backend=new MultiHartBackend {
      def holdReset(h: Int): Unit = fail("held reset before validating probes")
      def writeMemory(a: Long,d: Array[Byte]): Unit = fail("loaded incomplete hart set")
      def boot(h: Int,e: Long): Unit = (); def release(h: Int): Unit = ()
      def step(c: Long): Unit = (); def completion(h: Int): Option[Status] = None
      def park(h: Int): Unit = ()
    }
    try intercept[IllegalArgumentException](MultiHartExecutor.run(context(root,inputs()),Map.empty,backend))
    finally org.apache.commons.io.FileUtils.deleteDirectory(root)
  }
}
