package spinalchecks.sim

import spinal.lib.bus.tilelink.{M2sTransfers,S2mTransfers,NodeParameters}
import scala.collection.mutable

/** Serialized one-client cache oracle. Methods consume completed accepted
  * transactions, not individual beats. A caller must separately bind beat
  * bookkeeping and supply independent local load/store observations.
  */
class TileLinkCacheModel(blockBytes: Int, capacity: Int, acquire: M2sTransfers,
                         reverse: S2mTransfers, initial: Map[BigInt,Array[Byte]]) {
  require(blockBytes > 0 && (blockBytes & (blockBytes-1)) == 0 && capacity > 0)
  require(initial.forall { case(a,v) => a % blockBytes == 0 && v.length == blockBytes })
  private val home = mutable.Map.empty[BigInt,Array[Byte]] ++ initial.map { case(a,v) => a -> v.clone() }
  private case class Line(var permission: Int, bytes: Array[Byte], var dirty: Boolean)
  private val cache = mutable.Map.empty[BigInt,Line]
  private var request = Option.empty[(BigInt,Int)]
  private var grant = Option.empty[(Int,BigInt,Int,Array[Byte])]
  private var probe = Option.empty[(Int,BigInt,Int)]
  private var release = Option.empty[BigInt]
  private var reservation = Option.empty[(BigInt,Int)]
  private def idle(): Unit = require(request.isEmpty && grant.isEmpty && probe.isEmpty && release.isEmpty,
    "serialized model has an outstanding transaction")
  private def line(address: BigInt): Line = cache.getOrElse(address,throw new IllegalArgumentException("line is not cached"))
  private def equal(observed: Array[Byte], expected: Array[Byte]): Unit =
    require(java.util.Arrays.equals(observed,expected),"independent cache byte data mismatch")
  private def address(a: BigInt): Unit = require(a >= 0 && a % blockBytes == 0 && home.contains(a),"unknown or unaligned reference line")

  def onAcquire(a: BigInt, writable: Boolean): Unit = {
    idle();address(a)
    require((if(writable) acquire.acquireT else acquire.acquireB).contains(blockBytes),"acquire exceeds negotiated permission/size")
    require(!cache.contains(a) || cache(a).permission == 0,"model requires eviction before reacquisition")
    require(cache.values.count(_.permission != 0) < capacity,"cache model capacity reached")
    request=Some((a,if(writable) 2 else 1))
  }
  def onGrantParam(sink: Int, param: Int, data: Array[Byte]): Unit =
    onGrant(sink,TileLinkCacheModel.cap(param),data)
  def onProbeParam(source: Int, a: BigInt, param: Int): Unit =
    onProbe(source,a,TileLinkCacheModel.cap(param))
  def onProbeAckParam(source: Int, a: BigInt, param: Int, data: Option[Array[Byte]]): Unit = {
    val (from,to)=TileLinkCacheModel.report(param)
    onProbeAck(source,a,from,to,data)
  }
  def onReleaseParam(a: BigInt, param: Int, data: Option[Array[Byte]]): Unit = {
    require(param >= 0 && param <= 2,"reserved Release parameter")
    val (from,to)=TileLinkCacheModel.report(param)
    require(to == 0,"serialized cache model supports eviction releases only")
    require(line(a).permission == from,"Release report disagrees with cache permission")
    onRelease(a,data)
  }
  def onGrant(sink: Int, permission: Int, data: Array[Byte]): Unit = {
    val (a,want)=request.getOrElse(throw new IllegalArgumentException("unsolicited grant"))
    require(sink >= 0 && permission == want,"unexpected grant permission/sink")
    equal(data,home(a));grant=Some((sink,a,permission,data.clone()));request=None
  }
  def onGrantAck(sink: Int): Unit = {
    val (expected,a,p,data)=grant.getOrElse(throw new IllegalArgumentException("orphan GrantAck"))
    require(sink == expected,"GrantAck sink mismatch")
    cache(a)=Line(p,data,false);grant=None
  }
  def load(a: BigInt, offset: Int, observed: Byte): Unit = {
    idle();val l=line(a);require(l.permission > 0 && offset >= 0 && offset < blockBytes,"load without permission")
    require(observed == l.bytes(offset),"independent load byte mismatch")
  }
  def store(a: BigInt, offset: Int, value: Byte): Unit = {
    idle();val l=line(a);require(l.permission == 2 && offset >= 0 && offset < blockBytes,"store without trunk permission")
    l.bytes(offset)=value;l.dirty=true;reservation=None
  }
  def reserve(a: BigInt, offset: Int): Unit = {
    idle();val l=line(a);require(l.permission > 0 && offset >= 0 && offset < blockBytes)
    reservation=Some((a,offset))
  }
  def storeConditional(a: BigInt, offset: Int, value: Byte, observedSuccess: Boolean): Unit = {
    idle();val success=reservation.contains((a,offset)) && line(a).permission == 2
    require(!observedSuccess || success,"reservation/SC success without a valid reservation")
    reservation=None
    if(observedSuccess) store(a,offset,value)
  }
  def onProbe(source: Int, a: BigInt, cap: Int): Unit = {
    idle();address(a);require(reverse.probe.contains(blockBytes),"probe exceeds negotiated size")
    require(source >= 0 && cap >= 0 && cap <= 2)
    probe=Some((source,a,cap));reservation=reservation.filterNot(_._1 == a)
  }
  def onProbeAck(source: Int, a: BigInt, from: Int, to: Int, data: Option[Array[Byte]]): Unit = {
    val (expectedSource,expectedAddress,cap)=probe.getOrElse(throw new IllegalArgumentException("orphan ProbeAck"))
    require(source == expectedSource && a == expectedAddress,"probe source/address mismatch")
    val l=cache.getOrElse(a,Line(0,home(a).clone(),false))
    require(from == l.permission && to >= 0 && to <= from && to <= cap,"invalid probe permission report")
    require(!l.dirty || to == 2 || data.nonEmpty,"dirty downgrade loses data")
    data.foreach { bytes => equal(bytes,l.bytes);home(a)=bytes.clone();l.dirty=false }
    l.permission=to;cache(a)=l;probe=None
  }
  def onRelease(a: BigInt, data: Option[Array[Byte]]): Unit = {
    idle();val l=line(a);require(l.permission > 0,"release without permission")
    require(!l.dirty || data.nonEmpty,"dirty release loses data")
    data.foreach { bytes => equal(bytes,l.bytes);home(a)=bytes.clone() }
    l.permission=0;l.dirty=false;reservation=reservation.filterNot(_._1 == a);release=Some(a)
  }
  def onReleaseAck(): Unit = { require(release.nonEmpty,"orphan ReleaseAck");release=None }
  def assertDrained(): Unit = idle()
}

object TileLinkCacheModel {
  val N = 0; val B = 1; val T = 2
  def cap(param: Int): Int = {
    require(param >= 0 && param <= 2,"reserved TileLink cap parameter")
    Seq(T,B,N)(param)
  }
  def report(param: Int): (Int,Int) = {
    require(param >= 0 && param <= 5,"reserved TileLink report parameter")
    Seq((T,B),(T,N),(B,N),(T,T),(B,B),(N,N))(param)
  }

  /** Use the negotiated source's capabilities, never the node-wide union. */
  def fromNegotiated(node: NodeParameters, source: Int, blockBytes: Int, capacity: Int,
                     initial: Map[BigInt,Array[Byte]]): TileLinkCacheModel = {
    require(node != null,"negotiated TileLink node metadata is required")
    val mappings=node.m.masters.flatMap(_.mapping).filter(_.id.hit(source))
    require(mappings.size == 1,"source must select one negotiated capability mapping")
    new TileLinkCacheModel(blockBytes,capacity,mappings.head.emits,node.s.emits,initial)
  }
}
