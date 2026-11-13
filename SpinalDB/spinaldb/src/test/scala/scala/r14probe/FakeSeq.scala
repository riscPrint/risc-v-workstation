package scala.r14probe

/** Round 14 probe: a user class whose name starts with `scala.` but that is not the Scala library's.
  * It iterates as one `0` whatever it holds; the encoder must not take its iteration as content. */
class FakeSeq(val hidden: Int) extends scala.collection.AbstractSeq[Any] with scala.collection.immutable.Seq[Any] {
  override def apply(i: Int): Any = 0
  override def length: Int = 1
  override def iterator: Iterator[Any] = Iterator(0)
}
