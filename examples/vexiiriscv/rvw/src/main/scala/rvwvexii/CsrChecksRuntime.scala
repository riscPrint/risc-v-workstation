package rvwvexii

import java.io.File
import spinal.core._
import spinal.core.sim._
import spinalchecks._
import riscvsim.{ElfFile, ToHost}
import vexiiriscv.{ParamSimple, VexiiRiscv}
import vexiiriscv.execute.lsu.LsuCachelessPlugin
import vexiiriscv.fetch.FetchCachelessPlugin
import vexiiriscv.misc.PrivilegedPlugin
import vexiiriscv.test.VexiiRiscvProbe
import scala.collection.mutable

object CsrChecksRuntime {
  def main(args: Array[String]): Unit = {
    require(args.length >= 4, "usage: CsrChecksRuntime model.json out none|read program.elf ...")
    val source = scala.io.Source.fromFile(args(0))
    val model = try ujson.read(source.mkString) finally source.close()
    require(model("schema").str == "rvw.csr/1" && model("xlen").num == 32)
    val scratch = model("csrs").arr.find(_("name").str == "mscratch").get
    require(scratch("address").num == 0x340 && scratch("privilege").str == "M")
    val fields = scratch("fields").arr
    require(fields.size == 1 && fields.head("lsb").num == 0 && fields.head("width").num == 32 &&
      fields.head("access")("M").str == "RW" && scratch("reset_known").bool == false)
    val out = new File(args(1)).getCanonicalFile
    require(Set("none", "read")(args(2)))
    val fault = args(2) == "read"
    val (config, checks) = SpinalChecks.install(VexiiTop.spinalConfig.copy(targetDirectory = new File(out,"rtl").getPath),
      ChecksConfig(mode = Mode.Both, enable = Seq("csr.*"), reportPath = new File(out,"checks.json").getPath))
    val compiled = SimConfig.withConfig(config).workspacePath(out.getPath).workspaceName("native")
      .withVerilator.addSimulatorFlag("--assert").compile {
    val plugins = VexiiTop.param("rv32im").plugins()
    plugins += new TrapTapPlugin
    plugins += new CsrChecksPlugin(fault)
    ParamSimple.setPma(plugins)
      VexiiRiscv(plugins)
    }
    require(checks.inserted.count(_.kind == "csr.read") == 1)
    for ((path,index) <- args.drop(3).zipWithIndex) {
      val elf = ElfFile(path)
      require(elf.xlen == 32 && elf.entry == 0x80000000L)
      val memory = mutable.LongMap.empty[Int]
      elf.load { (base,bytes) => bytes.indices.foreach(i => memory(base+i) = bytes(i) & 255) }
      def word(address: Long, bytes: Int): BigInt = (0 until bytes).foldLeft(BigInt(0))((v,i) =>
        v | (BigInt(memory.getOrElse(address+i,0)) << (8*i)))
      val host = new ToHost(ToHost.find(elf).get,4)
      compiled.doSim(name=s"program_$index") { dut =>
        val cd=dut.clockDomain
        val priv=dut.host[PrivilegedPlugin].logic.harts(0)
        val tap=dut.host[TrapTapPlugin].logic
        val ibus=dut.host[FetchCachelessPlugin].logic.bus
        val dbus=dut.host[LsuCachelessPlugin].logic.bus
        val ibytes=ibus.p.dataWidth/8
        val dbytes=dbus.p.dataWidth/8
        val fetch=mutable.Queue.empty[(BigInt,Int)]
        val data=mutable.Queue.empty[(BigInt,Int)]
        val traps=mutable.Queue.empty[(BigInt,BigInt)]
        var retired=0L
        var cycle=0L
        var done=Option.empty[Long]
        priv.int.m.timer #= false;priv.int.m.software #= false;priv.int.m.external #= false
        dut.host[PrivilegedPlugin].logic.rdtime #= 0
        ibus.cmd.ready #= true;ibus.rsp.valid #= false;ibus.rsp.word #= 0;ibus.rsp.error #= false;ibus.rsp.id #= 0
        dbus.cmd.ready #= true;dbus.rsp.valid #= false;dbus.rsp.data #= 0;dbus.rsp.error #= false;dbus.rsp.id #= 0
        val backend=new C2Backend(32,()=>cycle,()=>tap.privilege.toInt & 3,
          ()=>if(traps.nonEmpty) traps.dequeue() else throw new IllegalStateException("missing trap observation"),
          _=>retired+=1, (_,_,_,_)=>(),
          (addr,size,value)=>{ if(host.onStore(addr,size,value).nonEmpty && done.isEmpty) done=Some(cycle) })
        cd.onSamplings { if(tap.fire.toBoolean) traps.enqueue((tap.epc.toBigInt,tap.tval.toBigInt)) }
        val probe=new VexiiRiscvProbe(dut,None,withRvls=false)
        probe.checkLiveness=false;probe.trace=false;probe.add(backend)
        cd.forkStimulus(10);cd.waitSampling(10)
        while(cycle < 20000 && done.forall(cycle < _+20)) {
          cd.waitFallingEdge()
          ibus.rsp.valid #= fetch.nonEmpty
          fetch.headOption.foreach { case(v,id)=>ibus.rsp.word #= v;ibus.rsp.id #= id }
          dbus.rsp.valid #= data.nonEmpty
          data.headOption.foreach { case(v,id)=>dbus.rsp.data #= v;dbus.rsp.id #= id }
          cd.waitSampling();cycle+=1
          dut.host[PrivilegedPlugin].logic.rdtime #= cycle
          if(fetch.nonEmpty) fetch.dequeue()
          if(data.nonEmpty) data.dequeue()
          if(ibus.cmd.valid.toBoolean && ibus.cmd.ready.toBoolean) {
            val address=ibus.cmd.address.toLong & ~(ibytes-1L)
            fetch.enqueue((word(address,ibytes),ibus.cmd.id.toInt))
          }
          if(dbus.cmd.valid.toBoolean && dbus.cmd.ready.toBoolean) {
            val cmd=dbus.cmd
            val address=cmd.address.toLong & ~(dbytes-1L)
            if(cmd.write.toBoolean) {
              for(i<-0 until dbytes if (cmd.mask.toInt & (1<<i))!=0)
                memory(address+i)=((cmd.data.toBigInt>>(8*i))&255).toInt
            }
            data.enqueue((if(cmd.write.toBoolean) BigInt(0) else word(address,dbytes),cmd.id.toInt))
          }
        }
        backend.drain()
        val fs=ChecksSim.firings(dut)
        ChecksSim.writeRunReport(dut,new File(out,s"run_$index.json").getPath,Seq(
          "status" -> Json.Str(if(done.nonEmpty && host.value==1) "pass" else "fail"),
          "elf" -> Json.Str(elf.file.getCanonicalPath),"elf_sha256" -> Json.Str(elf.sha256),
          "cycles" -> Json.Num(BigDecimal(cycle)),"retired" -> Json.Num(BigDecimal(retired))))
        require(done.nonEmpty && host.value==1,s"program failed: tohost=${host.value}")
        if(!fault) require(fs.isEmpty,fs.map(_.check.id).mkString(","))
        if(fault && index==0) require(fs.exists(_.check.kind=="csr.read"),"read fault was not detected")
      }
    }
    println("VEXII_CSR_CHECKS_RUNTIME_OK")
  }
}
