package riscvsim

import com.sun.jna.{Function, Memory, Native, NativeLibrary, Pointer}
import java.io.File

/** Host binding for DeviceApiV1. The caller serializes operations at sampled boundaries.
  * Device maps and interrupt routing remain in the project adapter. */
final class PluginDevice(path: File, config: String, seed: Long) extends AutoCloseable {
  private val library = PluginDevice.library(path)
  private val api = library.getFunction("rvw_device_plugin_v1").invokePointer(Array.empty[Object])
  require(api != null && api.getInt(0) == 1, "unsupported device plugin ABI")
  private val first = ((4 + Native.POINTER_SIZE - 1) / Native.POINTER_SIZE) * Native.POINTER_SIZE
  private def function(index: Int): Function = {
    val pointer = api.getPointer(first + index.toLong * Native.POINTER_SIZE)
    require(pointer != null, "missing device plugin callback")
    Function.getFunction(pointer)
  }
  private val functions = (0 until 8).map(function)
  private var handle = functions(0).invokePointer(Array[Object](config, Long.box(seed)))
  require(handle != null, "device plugin initialization failed")
  private def call(index: Int, args: Object*): Int = {
    require(handle != null, "device is closed")
    val code = functions(index).invokeInt((Seq[Object](handle) ++ args).toArray)
    require(code == 0, s"device plugin callback $index failed: $code")
    code
  }
  def read(offset: Long, bytes: Int): BigInt = {
    require(bytes >= 1 && bytes <= 8, "device access width must be 1..8")
    val value = new Memory(8)
    call(2, Long.box(offset), Int.box(bytes), value)
    BigInt(1, value.getByteArray(0, 8).reverse)
  }
  def write(offset: Long, bytes: Int, value: BigInt, mask: BigInt): Unit = {
    require(bytes >= 1 && bytes <= 8, "device access width must be 1..8")
    call(3, Long.box(offset), Int.box(bytes), Long.box(value.toLong), Long.box(mask.toLong))
  }
  def tick(cycle: Long): BigInt = {
    call(4, Long.box(cycle))
    val bits = functions(5).invokeLong(Array[Object](handle))
    BigInt(bits) & ((BigInt(1) << 64) - 1)
  }
  def close(): Unit = if (handle != null) {
    functions(1).invokeVoid(Array[Object](handle))
    handle = null
  }
}
object PluginDevice {
  // Keep libraries loaded for the process lifetime. CPython owns process-global state.
  private val libraries = new java.util.concurrent.ConcurrentHashMap[String, NativeLibrary]()
  private def library(path: File): NativeLibrary =
    libraries.computeIfAbsent(path.getCanonicalPath, p => NativeLibrary.getInstance(p))
}
