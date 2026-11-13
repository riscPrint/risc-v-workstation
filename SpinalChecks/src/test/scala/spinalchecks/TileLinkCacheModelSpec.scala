package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.lib.bus.tilelink._
import spinal.lib.bus.misc.SizeMapping
import spinalchecks.sim.TileLinkCacheModel

class TileLinkCacheModelSpec extends AnyFunSuite {
  def model() = new TileLinkCacheModel(4,2,M2sTransfers(acquireT=SizeRange(4),acquireB=SizeRange(4)),
    S2mTransfers(probe=SizeRange(4)),Map(BigInt(0)->Array[Byte](1,2,3,4)))
  def obtain(m:TileLinkCacheModel):Unit={m.onAcquire(0,true);m.onGrantParam(2,0,Array[Byte](1,2,3,4));m.onGrantAck(2)}
  test("dirty probes, release writeback, reacquisition and reservation loss") {
    val m=model();obtain(m);m.load(0,0,1);m.store(0,1,9);m.reserve(0,0)
    m.onProbeParam(3,0,1);m.onProbeAckParam(3,0,0,Some(Array[Byte](1,9,3,4)))
    m.storeConditional(0,0,8,false);m.onReleaseParam(0,2,None);m.onReleaseAck()
    m.onAcquire(0,true);m.onGrant(1,2,Array[Byte](1,9,3,4));m.onGrantAck(1)
    m.reserve(0,0);m.storeConditional(0,0,8,true)
    m.onReleaseParam(0,1,Some(Array[Byte](8,9,3,4)));m.onReleaseAck();m.assertDrained()
  }
  test("seeded data, ownership, reservation and transaction faults are rejected") {
    val a=model();a.onAcquire(0,true)
    intercept[IllegalArgumentException](a.onGrant(0,2,Array[Byte](9,2,3,4)))
    val b=model();b.onAcquire(0,true);b.onGrant(2,2,Array[Byte](1,2,3,4))
    intercept[IllegalArgumentException](b.onGrantAck(3))
    val c=model();obtain(c);c.store(0,0,9);c.onProbe(0,0,0)
    intercept[IllegalArgumentException](c.onProbeAck(0,0,2,0,None))
    val d=model();obtain(d);d.onProbe(0,0,0)
    intercept[IllegalArgumentException](d.onProbeAck(1,0,2,0,None))
    val e=model();obtain(e)
    intercept[IllegalArgumentException](e.storeConditional(0,0,9,true))
    val f=model();obtain(f);f.store(0,0,9)
    intercept[IllegalArgumentException](f.onRelease(0,None))
    val g=model();obtain(g);g.reserve(0,0);g.storeConditional(0,0,9,false);g.load(0,0,1)
    intercept[IllegalArgumentException](model().onGrantAck(0))
    intercept[IllegalArgumentException](model().onReleaseAck())
  }
  test("capabilities are source specific and missing metadata is not accepted") {
    val emit=M2sTransfers(acquireB=SizeRange(4))
    val m=M2sParameters(32,32,Seq(M2sAgent(null,Seq(M2sSource(SizeMapping(0,1),emit)))))
    val s=S2mParameters(Seq(S2mAgent(null,SizeMapping(0,1),S2mTransfers(probe=SizeRange(4)))))
    val ref=TileLinkCacheModel.fromNegotiated(NodeParameters(m,s),0,4,1,Map(BigInt(0)->Array[Byte](1,2,3,4)))
    intercept[IllegalArgumentException](ref.onAcquire(0,true))
    ref.onAcquire(0,false);ref.onGrant(0,1,Array[Byte](1,2,3,4));ref.onGrantAck(0)
    intercept[IllegalArgumentException](ref.store(0,0,9))
    intercept[IllegalArgumentException](TileLinkCacheModel.fromNegotiated(null,0,4,1,Map.empty))
    intercept[IllegalArgumentException](TileLinkCacheModel.fromNegotiated(NodeParameters(m,s),1,4,1,Map.empty))
  }
}
