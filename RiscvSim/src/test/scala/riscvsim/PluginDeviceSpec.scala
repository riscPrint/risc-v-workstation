package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import scala.sys.process._

class PluginDeviceSpec extends AnyFunSuite {
  test("DeviceApiV1 host binding isolates handles and rejects callback failures") {
    val dir = Files.createTempDirectory("rvw-device-jna").toFile
    val source = new java.io.File(dir, "plugin.c")
    val code = """#include <stdint.h>
#include <stdlib.h>
struct api { uint32_t abi; void* (*create)(const char*,uint64_t); void (*destroy)(void*);
 int (*read)(void*,uint64_t,uint32_t,uint64_t*); int (*write)(void*,uint64_t,uint32_t,uint64_t,uint64_t);
 int (*tick)(void*,uint64_t); uint64_t (*irq)(void*); size_t (*snapshot)(void*,uint8_t*,size_t); int (*restore)(void*,const uint8_t*,size_t); };
void* create(const char* c,uint64_t s){ uint64_t* p=malloc(8); *p=s; return p; }
void destroy(void* p){free(p);}
int read_(void* p,uint64_t a,uint32_t n,uint64_t* v){ if(a)return 1; *v=*(uint64_t*)p;return 0;}
int write_(void* p,uint64_t a,uint32_t n,uint64_t v,uint64_t m){*(uint64_t*)p=v;return 0;}
int tick(void* p,uint64_t c){return 0;}
uint64_t irq(void* p){return *(uint64_t*)p;}
size_t snapshot(void* p,uint8_t* v,size_t n){return 0;}
int restore(void* p,const uint8_t* v,size_t n){return 1;}
struct api api={1,create,destroy,read_,write_,tick,irq,snapshot,restore};
const struct api* rvw_device_plugin_v1(){return &api;}
"""
    Files.writeString(source.toPath, code)
    val lib = new java.io.File(dir, "plugin.so")
    assert(Seq("cc", "-shared", "-fPIC", source.getPath, "-o", lib.getPath).! == 0)
    val a = new PluginDevice(lib, "{}", 7)
    val b = new PluginDevice(lib, "{}", 9)
    try {
      assert(a.read(0, 8) == 7 && b.read(0, 8) == 9)
      a.write(0, 8, BigInt(11), BigInt(255))
      assert(a.tick(100) == 11 && b.tick(100) == 9)
      intercept[IllegalArgumentException](a.read(8, 8))
    } finally { a.close(); b.close() }
    a.close()
    intercept[IllegalArgumentException](a.read(0, 8))
  }
}
