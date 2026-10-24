package scala.r14probe

/** Round 14 probe: a user class whose name starts with `scala.` but that is not the Scala library's.
  * It iterates as one `0` whatever it holds; the encoder must not take its iteration as content. */
class FakeSeq(val hidden: Int) extends scala.collection.immutable.AbstractSeq[Any] {
  def apply(i: Int): Any = 0
  def length: Int = 1
  def iterator: Iterator[Any] = Iterator(0)
}
