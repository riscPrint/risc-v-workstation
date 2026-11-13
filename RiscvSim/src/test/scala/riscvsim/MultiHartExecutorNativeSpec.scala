package riscvsim

import java.io.File
import java.nio.{ByteBuffer,ByteOrder}
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import scala.sys.process._

/** Three subset harts share one serialized physical RAM. No production core is built. */
class ExecutorNativeTop extends Component {
  val io = new Bundle { val instructions = in Vec(Bits(32 bits),3); val enable = in Bits(3 bits) }
  val harts=Seq.fill(3)(new FixtureHart(Seq(0L,0L),programmable=true,xlen=64))
  val memory=Mem(Bits(64 bits),3)
  val turn=Reg(UInt(2 bits)) init 0
  turn := turn+1
  when(turn===2) { turn:=0 }
  for((h,id)<-harts.zipWithIndex) {
    h.io.instruction:=io.instructions(id); h.io.enable:=io.enable(id); h.io.ready:=turn===id
    val word=(h.io.address>>3).resize(2)
    h.io.rdata:=memory.readAsync(word)
    when(h.io.request && h.io.ready && h.io.write) { memory.write(word,h.io.wdata) }
    h.io.simPublic(); h.pc.simPublic()
  }
  memory.simPublic()
}

class MultiHartExecutorNativeSpec extends AnyFunSuite {
  private def image(root: File,hart: Int): ElfFile = {
    val entry=0x1000L+hart*0x1000
    val words=Seq(((37L+hart)<<20)|(1<<7)|0x13,
      ((hart*8L>>5)<<25)|(1<<20)|(3<<12)|((hart*8L&31)<<7)|0x23,
      (3L<<12)|(2<<7)|3)
    val bytes=new Array[Byte](268)
    val b=ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    b.putInt(0,0x464c457f); bytes(4)=2; bytes(5)=1
    b.putShort(16,2.toShort); b.putShort(18,243.toShort)
    b.putLong(24,entry); b.putLong(32,64); b.putShort(54,56.toShort); b.putShort(56,2.toShort)
    b.putInt(64,1); b.putLong(72,256); b.putLong(80,entry); b.putLong(88,entry)
    b.putLong(96,12); b.putLong(104,12)
    b.putInt(120,1); b.putLong(128,268); b.putLong(136,0); b.putLong(144,0)
    b.putLong(152,0); b.putLong(160,24)
    words.zipWithIndex.foreach { case(w,i)=>b.putInt(256+i*4,w.toInt) }
    val file=new File(root,s"hart-$hart.elf"); Files.write(file.toPath,bytes); new ElfFile(file)
  }
  test("generic executor loads three ELF images and captures real per-hart RTL retirement") {
    val root=Files.createTempDirectory("multi-hart-executor-native").toFile
    val images=new HartImages((0 until 3).map(h=>h->image(root,h)),64)
    val ctx=new MultiHartExecutorSpec().context(root,images,200)
    val compiled=SimConfig.withVerilator.workspacePath(new File(root,"sim").getPath).compile(new ExecutorNativeTop)
    try {
      compiled.doSim(seed=7) { dut =>
        dut.io.enable #= 0; dut.io.instructions.foreach(_ #= 0)
        dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(20)
        val loaded=scala.collection.mutable.Map.empty[Long,Byte]
        val entries=scala.collection.mutable.Map.empty[Int,Long]
        val released=scala.collection.mutable.Set.empty[Int]
        val counts=Array.fill(3)(0)
        var captured=Vector.empty[(Int,RvfiRecord)]
        var serial=0L
        val reference=new SerializedMemoryReference(Seq.fill[Byte](24)(0))
        def bytes(value: BigInt)=(0 until 8).map(i=>((value>>(8*i))&255).toByte)
        val probes=dut.harts.zipWithIndex.map { case(h,id)=>id->new RvfiProbe(Nil) {
          override def sample(cycle: Long): Seq[RvfiRecord] = {
            if(!h.io.retired.toBoolean) Nil else {
              val insn=h.io.insn.toLong; val opcode=(insn&127).toInt
              val rs1=((insn>>15)&31).toInt
              val rs2=if(opcode==35) ((insn>>20)&31).toInt else 0
              val rd=if(opcode==35) 0 else ((insn>>7)&31).toInt
              val read=opcode==3; val write=opcode==35
              val result=if(read) h.io.rdata.toBigInt else if(opcode==19) BigInt(insn.toInt>>20) else BigInt(0)
              val pc=h.io.pc.toBigInt
              val r=RvfiRecord(counts(id),cycle,insn,false,false,false,3,2,rs1,h.io.registers(rs1).toBigInt,
                rs2,h.io.registers(rs2).toBigInt,rd,result,pc,pc+4,
                if(read||write) h.io.address.toBigInt else BigInt(0),if(read)255 else 0,if(write)255 else 0,
                if(read)h.io.rdata.toBigInt else BigInt(0),if(write)h.io.wdata.toBigInt else BigInt(0),false)
              counts(id)+=1; captured :+= id->r; Seq(r)
            }
          }
        }}.toMap
        val backend=new MultiHartBackend {
          def holdReset(h: Int): Unit = { dut.clockDomain.assertReset(); dut.clockDomain.waitRisingEdge(2) }
          def writeMemory(a: Long,d: Array[Byte]): Unit = {
            assert(released.isEmpty)
            d.indices.foreach(i=>loaded(a+i)=d(i))
            for(w<-0 until 3 if (0 until 8).forall(i=>loaded.contains(w*8L+i))) {
              val data=(0 until 8).map(i=>BigInt(loaded(w*8L+i)&255)<<(8*i)).sum
              dut.memory.setBigInt(w,data)
            }
          }
          def boot(h: Int,entry: Long): Unit = { entries(h)=entry }
          def release(h: Int): Unit = {
            released+=h
            if(released.size==3) {
              assert(entries.size==3 && (0 until 24).forall(i=>loaded.get(i.toLong).contains(0.toByte)))
              dut.clockDomain.deassertReset()
              entries.foreach { case(id,pc)=>dut.harts(id).pc #= pc }
              dut.io.enable #= 7
            }
          }
          def step(cycle: Long): Unit = {
            dut.clockDomain.waitFallingEdge()
            captured=Vector.empty
            for((h,id)<-dut.harts.zipWithIndex) {
              val pc=h.io.pc.toLong
              val insn=(0 until 4).map(i=>(loaded.getOrElse(pc+i,0.toByte).toLong&255)<<(8*i)).sum
              dut.io.instructions(id) #= insn
            }
            sleep(1)
          }
          def completion(h: Int): Option[Status] = if(dut.harts(h).io.pc.toLong==entries(h)+12) {
            assert(dut.harts(h).io.registers(2).toBigInt==37,"shared producer value")
            Some(Status.Pass)
          } else None
          def park(h: Int): Unit = { dut.io.enable #= (dut.io.enable.toInt & ~(1<<h)) }
          override def observe(cycle: Long,session: MultiHartSession): Unit = captured.foreach { case(h,r)=>
            if(r.memRmask!=0 || r.memWmask!=0) {
              val id=s"h$h-${r.order}"; val address=r.memAddr.toInt
              val from=if(r.memWmask!=0) {
                reference.write(serial,id,address,bytes(BigInt(37+h)),bytes(r.memWdata),255); Vector.empty[String]
              } else reference.read(serial,id,address,bytes(r.memRdata))
              session.memory(cycle,id,if(r.memWmask!=0)"write" else "read",ujson.Obj(
                "source"->s"hart-$h","address"->Hex(r.memAddr),"data"->Hex(if(r.memWmask!=0)r.memWdata else r.memRdata),
                "mask"->"0xff","boundary"->"executor-shared","serialization"->serial.toString,
                "hart"->h,"order"->r.order.toString,"read_from"->ujson.Arr.from(from)))
              serial+=1
            }
          }
        }
        val outcome=MultiHartExecutor.run(ctx,probes,backend)
        assert(outcome.status==Status.Pass && outcome.instret==9 && serial==6)
        assert((0 until 3).map(dut.memory.getBigInt(_))==Seq(37,38,39))
      }
      val ref=new File(root,"reference.json")
      Files.writeString(ref.toPath,ujson.write(ujson.Obj("schema"->"rvw.serialized-memory/1","boundary"->"executor-shared",
        "initial"->ujson.Arr(ujson.Obj("address"->"0x0","bytes"->("00"*24))),
        "writes"->ujson.Obj.from((0 until 3).map(h=>s"h$h-1"->ujson.Obj("address"->Hex(BigInt(h*8)),"data"->Hex(BigInt(37+h)),"mask"->"0xff"))))))
      val tools=new File(sys.props("riscvsim.tools"))
      val check=Seq(new File(tools,"rvw/.venv/bin/python").getPath,"-m","rvw","memory","check",
        "--trace",new File(root,"rvfi.jsonl").getPath,"--reference",ref.getPath)
      val result=ujson.read(Process(check,tools).!!)
      assert(result("status").str=="consistent" && result("checks").num==6)
    } finally org.apache.commons.io.FileUtils.deleteDirectory(root)
  }
}
