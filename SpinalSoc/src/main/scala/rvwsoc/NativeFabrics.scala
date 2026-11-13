package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba4.axi._
import spinal.lib.bus.misc.SizeMapping
import spinal.lib.bus.tilelink
import spinal.lib.system.tag.{MappedNode,MappedTransfers}

object NativeWindows {
  def gaps(windows: Seq[SizeMapping], width: Int): Seq[SizeMapping] = {
    val result=scala.collection.mutable.ArrayBuffer[SizeMapping]()
    var cursor=BigInt(0)
    def gap(end: BigInt): Unit = while(cursor<end) {
      var size=BigInt(1)<<((end-cursor).bitLength-1)
      while(cursor%size!=0) size=size>>1
      result += SizeMapping(cursor,size)
      cursor += size
    }
    for(w <- windows.sortBy(_.base)) { gap(w.base);cursor=w.base+w.size }
    gap(BigInt(1)<<width)
    result.toList
  }
  def check(windows: Seq[SizeMapping], width: Int): Unit = {
    require(windows.nonEmpty)
    for(w <- windows) require(w.base >= 0 && w.size > 0 && (w.size & (w.size-1)) == 0 &&
      w.base % w.size == 0 && w.base+w.size <= (BigInt(1)<<width), "native windows must be aligned powers of two")
    for(i <- windows.indices; j <- 0 until i)
      require(windows(i).base >= windows(j).base+windows(j).size ||
              windows(j).base >= windows(i).base+windows(i).size, "native windows must not overlap")
  }
}

/** Per-master decoders and per-slave arbiters. AXI target addresses stay global. */
class NativeAxiCrossbar(config: Axi4Config, masterCount: Int, windows: Seq[SizeMapping]) extends Component {
  require(masterCount>0)
  NativeWindows.check(windows,config.addressWidth)
  val outputIdWidth=(if(config.useId) config.idWidth else 0)+log2Up(masterCount)
  val outputConfig=config.copy(useId=outputIdWidth>0,idWidth=if(outputIdWidth>0) outputIdWidth else -1,
    readIssuingCapability=(config.readIssuingCapability max 1)*masterCount,
    writeIssuingCapability=(config.writeIssuingCapability max 1)*masterCount,
    combinedIssuingCapability=(config.combinedIssuingCapability max 2)*masterCount)
  val io=new Bundle {
    val inputs=Vec(slave(Axi4(config)),masterCount)
    val outputs=Vec(master(Axi4(outputConfig)),windows.size)
  }
  val fabric=Axi4CrossbarFactory()
  fabric.addSlaves(io.outputs.toSeq.zip(windows):_*)
  io.inputs.foreach(input => fabric.addConnection(input,io.outputs.toSeq))
  fabric.build()
  io.inputs.foreach(ProtocolChecks(_));io.outputs.foreach(ProtocolChecks(_))
}

/** Get/Put native crossbar. Each target receives its local window offset. */
class NativeTileLinkCrossbar(node: tilelink.NodeParameters, masterCount: Int, windows: Seq[SizeMapping]) extends Component {
  require(masterCount>0 && !node.withBCE,"native profile supports Get/Put without BCE")
  NativeWindows.check(windows,node.m.addressWidth)
  windows.foreach(w => require(w.size>=node.sizeBytes,"TileLink windows must cover the maximum transfer size"))
  val branchNodes=windows.map(w => node.copy(m=node.m.copy(addressWidth=log2Up(w.size))))
  val targetNodes=branchNodes.map(p => tilelink.Arbiter.downNodeFrom(Seq.fill(masterCount)(p)))
  val io=new Bundle {
    val inputs=Vec(slave(tilelink.Bus(node)),masterCount)
    val outputs=Vec(targetNodes.map(p => master(tilelink.Bus(p))))
  }
  val misses=NativeWindows.gaps(windows,node.m.addressWidth)
  def spec(mapping: spinal.lib.bus.misc.AddressMapping,p: tilelink.NodeParameters) =
    tilelink.DecoderDownSpec(Seq(MappedTransfers(MappedNode(this,mapping,Nil),node.m.emits)),Nil,p)
  val decoders=io.inputs.map { input =>
    val decoder=tilelink.Decoder(node,windows.zip(branchNodes).map{case(w,p) => spec(w,p)} :+ tilelink.DecoderDownSpec(
      misses.map(w => MappedTransfers(MappedNode(this,w,Nil),node.m.emits)),Nil,node))
    decoder.io.up << input
    val error=new tilelink.ErrorSlave(node.toBusParameter())
    error.io.bus << decoder.io.downs.last
    decoder
  }
  for(j <- windows.indices) {
    val arbiter=tilelink.Arbiter(Seq.fill(masterCount)(branchNodes(j)),targetNodes(j))
    for(i <- 0 until masterCount) arbiter.io.ups(i) << decoders(i).io.downs(j)
    io.outputs(j) << arbiter.io.down
  }
  io.inputs.foreach(ProtocolChecks(_));io.outputs.foreach(ProtocolChecks(_))
}

/** IDs and original bursts are retained by the SDK boundary adapters.
  * Public downstream requests use ID zero. Exclusive accesses are excluded.
  */
class AxiDataWidth(config: Axi4Config, width: Int) extends Component {
  require(Set(32,64,128).contains(config.dataWidth) && Set(32,64,128).contains(width))
  require(!config.useLock,"width conversion requires an interface without exclusive accesses")
  require(config.useLen && config.useSize && config.useLast && config.useStrb && config.useResp,
    "width conversion needs LEN, SIZE, LAST, STRB and RESP")
  val outputConfig=if(width==config.dataWidth) config else config.copy(dataWidth=width,useId=true,idWidth=1,
    useBurst=true,readIssuingCapability=8*((config.dataWidth max width)/(config.dataWidth min width)),
    writeIssuingCapability=8*((config.dataWidth max width)/(config.dataWidth min width)),
    combinedIssuingCapability=16*((config.dataWidth max width)/(config.dataWidth min width)))
  val io=new Bundle { val up=slave(Axi4(config));val down=master(Axi4(outputConfig)) }
  private def link(source: Axi4,target: Axi4): Unit = {
    require(source.config.dataWidth==target.config.dataWidth)
    target.ar.arbitrationFrom(source.ar);target.ar.payload.assignSomeByName(source.ar.payload)
    target.aw.arbitrationFrom(source.aw);target.aw.payload.assignSomeByName(source.aw.payload)
    if(target.config.useId && !source.config.useId) { target.ar.id:=0;target.aw.id:=0 }
    if(target.config.useLen && !source.config.useLen) { target.ar.len:=0;target.aw.len:=0 }
    if(target.config.useBurst && !source.config.useBurst) {
      target.ar.burst:=B(1,2 bits);target.aw.burst:=B(1,2 bits)
    }
    target.w << source.w
    source.r.arbitrationFrom(target.r);source.r.payload.assignSomeByName(target.r.payload)
    source.b.arbitrationFrom(target.b);source.b.payload.assignSomeByName(target.b.payload)
  }
  if(width==config.dataWidth) link(io.up,io.down)
  else {
    val serial=Axi4IdRemover(io.up)
    val read=new Axi4ReadOnlyUnburster(serial.config)
    val write=new Axi4WriteOnlyUnburster(serial.config)
    read.io.input << serial.toReadOnly();write.io.input << serial.toWriteOnly()
    val scalar=Axi4(serial.config.copy(useLen=false,useBurst=false))
    scalar << read.io.output;scalar << write.io.output
    val normalized=Axi4(scalar.config.copy(useLen=true))
    link(scalar,normalized)
    if(width<config.dataWidth) {
      val convert=Axi4Downsizer(normalized.config,normalized.config.copy(dataWidth=width))
      link(normalized,convert.io.input);link(convert.io.output,io.down)
      // Keep earlier narrow errors until the wide response is accepted.
      val readError=Reg(Bits(2 bits)) init(0)
      val writeError=Reg(Bits(2 bits)) init(0)
      val combinedRead=readError | io.down.r.resp
      val combinedWrite=writeError | io.down.b.resp
      when(io.down.r.fire) { readError:=combinedRead }
      when(normalized.r.fire) { readError:=0 }
      when(io.down.b.fire) { writeError:=combinedWrite }
      when(normalized.b.fire) { writeError:=0 }
      normalized.r.resp.removeAssignments() := combinedRead
      normalized.b.resp.removeAssignments() := combinedWrite
    } else {
      // The SDK upsizer stores an ID field even for one ordered ID.
      val tagged=Axi4(normalized.config.copy(useId=true,idWidth=1))
      link(normalized,tagged)
      val convert=Axi4Upsizer(tagged.config,tagged.config.copy(dataWidth=width),4)
      link(tagged,convert.io.input);link(convert.io.output,io.down)
    }
    when(io.down.r.valid) { assert(io.down.r.id===0,"width target returned an unknown read ID") }
    when(io.down.b.valid) { assert(io.down.b.id===0,"width target returned an unknown write ID") }
  }
  ProtocolChecks(io.up);ProtocolChecks(io.down)
}

object NativeFixtureConfig {
  def axi(width: Int=32)=Axi4Config(32,width,idWidth=1,useLock=false,useQos=false,useRegion=false,
    readIssuingCapability=2,writeIssuingCapability=2,combinedIssuingCapability=4)
  val windows=Seq(SizeMapping(0x1000,4096),SizeMapping(0x2000,4096))
  def tl=tilelink.M2sParameters(32,32,List(tilelink.M2sAgent(null,
    tilelink.M2sSource(SizeMapping(0,4),tilelink.M2sTransfers(get=tilelink.SizeRange.upTo(64),
      putFull=tilelink.SizeRange.upTo(64),putPartial=tilelink.SizeRange.upTo(64)))))).toNodeParameters()
}
class NativeAxiFabricFixture extends NativeAxiCrossbar(NativeFixtureConfig.axi(),2,NativeFixtureConfig.windows)
class NativeTlFabricFixture extends NativeTileLinkCrossbar(NativeFixtureConfig.tl,2,NativeFixtureConfig.windows)
class NativeWidthDownFixture extends AxiDataWidth(NativeFixtureConfig.axi(64),32)
class NativeWidthUpFixture extends AxiDataWidth(NativeFixtureConfig.axi(32),64)
object NativeFabricGenerate extends App {
  val directory=args(0)
  Seq[(String,()=>Component)]("axi"->(()=>new NativeAxiFabricFixture),"tl"->(()=>new NativeTlFabricFixture),
    "down"->(()=>new NativeWidthDownFixture),"up"->(()=>new NativeWidthUpFixture)).foreach { case(name,make) =>
    SpinalConfig(targetDirectory=directory+"/"+name).generateVerilog(make())
  }
}
