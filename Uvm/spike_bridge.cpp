// DPI transport for the versioned Spike shim. The runner verifies its manifest.
#include <svdpi.h>
#include <dlfcn.h>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>
#include "spike_effect.h"
namespace {
void *library=nullptr, *machine=nullptr;
int (*step_fn)(void*,Effect*,uint64_t,uint64_t,uint64_t,int);
void (*destroy_fn)(void*);
unsigned xlen;
bool aligned;
uint64_t registers[32]{};
std::string error;
template<class T> T symbol(const char* name) { return reinterpret_cast<T>(dlsym(library,name)); }
uint64_t mask(uint64_t lanes) { uint64_t v=0; for(unsigned i=0;i<8;i++) if((lanes>>i)&1) v|=uint64_t(255)<<(8*i); return v; }
}
extern "C" const char* rvw_uvm_error() { return error.c_str(); }
extern "C" void rvw_uvm_close() {
 if(machine && destroy_fn) destroy_fn(machine);
 machine=nullptr;
 if(library) dlclose(library);
 library=nullptr;
}
extern "C" int rvw_uvm_init(const char* lib,const char* source_hash,const char* build_hash,
 const char* isa,const char* modes,unsigned bits,unsigned pmp,int absent_zero,int align,
 unsigned long long base,unsigned long long size,unsigned long long pc,const char* image) {
 rvw_uvm_close(); error="initialization failed"; xlen=bits; aligned=align;
 std::memset(registers,0,sizeof(registers));
 library=dlopen(lib,RTLD_NOW|RTLD_LOCAL); if(!library) { error=dlerror(); return -1; }
 auto version=symbol<unsigned(*)()>("rvw_shim_version");
 auto source=symbol<const char*(*)()>("rvw_shim_source_sha256");
 auto build=symbol<const char*(*)()>("rvw_shim_build_sha256");
 auto create=symbol<void*(*)(const char*,const uint64_t*,size_t,const uint64_t*,size_t,uint64_t,unsigned,const char*,int,int)>("rvw_create");
 auto write=symbol<int(*)(void*,uint64_t,const uint8_t*,size_t)>("rvw_write");
 step_fn=symbol<decltype(step_fn)>("rvw_step"); destroy_fn=symbol<decltype(destroy_fn)>("rvw_destroy");
 if(!version || !source || !build || !create || !write || !step_fn || !destroy_fn ||
 version()!=4 || source_hash!=std::string(source()) || build_hash!=std::string(build())) { error="shim identity mismatch"; return -1; }
 uint64_t ram[]={base,size}; machine=create(isa,ram,1,nullptr,0,pc,pmp,modes,0,absent_zero);
 if(!machine) return -1;
 std::ifstream input(image); uint64_t addr,value;
 while(input>>std::hex>>addr>>value) { uint8_t byte=value; if(write(machine,addr,&byte,1)) return -1; }
 if(!input.eof()) { error="invalid memory image"; return -1; }
 return 0;
}
extern "C" int rvw_uvm_check(const svOpenArrayHandle data) {
 // Values come from the captured DUT, through a UVM analysis subscriber.
 if(!machine || svSize(data,1)!=19) { error="invalid bridge state or record width"; return -1; }
 uint64_t a[19]; for(int i=0;i<19;i++) a[i]=*static_cast<uint64_t*>(svGetArrElemPtr1(data,i));
 Effect e{};
 if(step_fn(machine,&e,0,0,0,0)) { auto why=symbol<const char*(*)()>("rvw_error"); error=why ? why() : "Spike step error"; return -1; }
 if(e.fd_valid || e.intr) { error="FP or interrupt needs the extended bridge profile"; return -1; }
 uint64_t xmask=xlen==32 ? 0xffffffffULL : ~0ULL;
 if(aligned && (e.mem_rmask||e.mem_wmask)) {
   unsigned shift=e.mem_addr%(xlen/8); e.mem_addr-=shift;
   e.mem_rmask<<=shift; e.mem_wmask<<=shift; e.mem_rdata<<=8*shift; e.mem_wdata<<=8*shift;
 }
 auto equal=[&](const char* field,uint64_t actual,uint64_t expected) {
   if(actual==expected) return true;
   char message[256]; snprintf(message,sizeof(message),"%s actual=0x%llx expected=0x%llx",field,(unsigned long long)actual,(unsigned long long)expected);
   error=message; return false;
 };
 const char* names[]={"pc","pc_next","insn","mode","rd","rd_wdata","mem_addr","mem_rmask","mem_wmask","mem_rdata","mem_wdata","trap","mem_fault"};
 uint64_t expected[]={e.pc&xmask,e.pc_next&xmask,e.insn,e.mode,e.rd,e.rd_wdata&xmask,e.mem_addr&xmask,e.mem_rmask,e.mem_wmask,e.mem_rdata,e.mem_wdata,e.trap,e.mem_fault};
 for(int i=0;i<13;i++) {
   if(i==5 && !e.rd) continue;
   if(i==6 && !(e.mem_rmask||e.mem_wmask||a[7]||a[8])) continue;
   uint64_t m=i==9 ? mask(e.mem_rmask) : i==10 ? mask(e.mem_wmask) : ~0ULL;
   if(!equal(names[i],a[i]&m,expected[i]&m)) return 1;
 }
 if(a[13]>31 || a[15]>31) { error="source register out of range"; return -1; }
 if(!equal("rs1_rdata",a[14],registers[a[13]]&xmask) ||
    !equal("rs2_rdata",a[16],registers[a[15]]&xmask)) return 1;
 // intr is the first instruction in the handler in C2, not an input level.
 static_cast<void>(a[17]);
 if(a[17] || a[18]) { error="handler/halt record unsupported"; return -1; }
 std::memcpy(registers,e.regs,sizeof(registers));
 return 0;
}
