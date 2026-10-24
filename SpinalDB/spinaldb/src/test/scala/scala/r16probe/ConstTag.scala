package scala.r16probe

/** A package name cannot make a user's constant disappear from a tag key. */
case class ConstTag() extends spinal.core.SpinalTag { final val payload = 16 }
