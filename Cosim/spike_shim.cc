// Uses only Spike's installed public C++ API. No simulator-private members.
#include <riscv/processor.h>
#include <riscv/mmu.h>
#include <riscv/disasm.h>
#include <riscv/simif.h>
#include <riscv/trap.h>
#include <array>
#include <cstring>
#include <cstdio>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unistd.h>

extern "C" {
struct Effect {
  uint64_t pc, pc_next, insn, mode, rd, rd_wdata;
  uint64_t mem_addr, mem_rmask, mem_wmask, mem_rdata, mem_wdata;
  uint64_t trap, intr, cause, tval, mem_fault, halted;
  uint64_t fd_valid, fd, fd_wdata, fflags, fcsr;
  uint64_t regs[32];
  char disasm[256];
};
}
struct Region { uint64_t base, size; };
struct Machine : simif_t {
  cfg_t cfg;
  std::string isa, privilege;
  std::vector<Region> ram, io;
  std::map<uint64_t, std::array<char,4096>> pages;
  std::map<size_t, processor_t*> harts;
  std::unique_ptr<processor_t> cpu;
  std::ostringstream sout;
  FILE* log = nullptr;
  uint64_t io_addr = 0, io_value = 0;
  bool inject = false;
  Machine(const char* instruction_set, const uint64_t* regions, size_t nr,
          const uint64_t* mmio, size_t ni, uint64_t pc, unsigned pmp,
          const char* modes, bool misaligned, bool absent_pmp_zero)
      : isa(instruction_set), privilege(modes) {
    cfg.isa = isa.c_str(); cfg.priv = privilege.c_str(); cfg.hartids = {0};
    cfg.pmpregions = pmp; cfg.misaligned = misaligned;
    cfg.mem_layout.clear();
    for (size_t i=0;i<nr;i++) { ram.push_back({regions[2*i],regions[2*i+1]});
      cfg.mem_layout.emplace_back(regions[2*i],regions[2*i+1]); }
    for (size_t i=0;i<ni;i++) io.push_back({mmio[2*i],mmio[2*i+1]});
    log = tmpfile(); if (!log) throw std::runtime_error("cannot create Spike diagnostic stream");
    cpu = std::make_unique<processor_t>(cfg.isa,cfg.priv,&cfg,this,0,false,log,sout);
    if(absent_pmp_zero) {
      if(pmp) throw std::runtime_error("absent PMP zero policy requires no PMP regions");
      auto* state=cpu->get_state();
      // const_csr_t keeps normal CSR privilege checks and ignores writes.
      for(unsigned addr=0x3a0;addr<=0x3ef;addr++) {
        if(addr<0x3b0 && cpu->get_xlen()==64 && (addr&1)) continue;
        state->add_csr(addr,std::make_shared<const_csr_t>(cpu.get(),addr,0));
      }
    }
    harts[0] = cpu.get();
    cpu->enable_log_commits(); cpu->set_debug(true);
    cpu->get_state()->pc = pc;
  }
  ~Machine() { cpu.reset(); if (log) fclose(log); }
  static bool contains(const Region& r, uint64_t a, size_t n=1) {
    return n <= r.size && a >= r.base && a-r.base <= r.size-n;
  }
  char* addr_to_mem(reg_t a) override {
    for (auto r:ram) if (contains(r,a)) return pages[a>>12].data()+(a&4095);
    return nullptr;
  }
  bool mmio_load(reg_t a,size_t n,uint8_t* out) override {
    for (auto r:io) if (contains(r,a,n)) {
      uint64_t v = inject && a==io_addr ? io_value : 0;
      for(size_t i=0;i<n;i++) out[i] = i<8 ? v>>(i*8) : 0;
      return true;
    }
    return false;
  }
  bool mmio_store(reg_t a,size_t n,const uint8_t*) override {
    for(auto r:io) if(contains(r,a,n)) return true;
    return false;
  }
  void proc_reset(unsigned) override {}
  const cfg_t& get_cfg() const override { return cfg; }
  const std::map<size_t,processor_t*>& get_harts() const override { return harts; }
  const char* get_symbol(uint64_t) override { return nullptr; }
  void step(Effect& e, uint64_t interrupt) {
    memset(&e,0,sizeof(e)); auto* s=cpu->get_state();
    e.pc=s->pc; e.mode=s->prv;
    try {
      auto fetch=cpu->get_mmu()->load_insn(s->pc);
      e.insn=fetch.insn.bits();
      if(fetch.insn.length()==2) e.insn &= 0xffff;
      else if(fetch.insn.length()==4) e.insn &= 0xffffffff;
      auto dis=cpu->get_disassembler()->disassemble(fetch.insn);
      snprintf(e.disasm,sizeof(e.disasm),"%s",dis.c_str());
    } catch(...) { snprintf(e.disasm,sizeof(e.disasm),"<instruction fetch fault>"); }
    // Refuse emulated split accesses before execution. A fault on the second
    // part could leave partial stores that scalar C2 cannot report.
    if(cfg.misaligned) {
      insn_t insn(e.insn);
      unsigned op=e.insn&0x7f, f=(e.insn>>12)&7, width=0, rs=0;
      int64_t offset=0;
      if((e.insn&3)==3 && (op==3 || op==7 || op==0x23 || op==0x27)) {
        width=1u<<(f&3); rs=insn.rs1();
        offset=(op==3 || op==7) ? insn.i_imm() : insn.s_imm();
      } else if((e.insn&3)!=3) {
        unsigned q=e.insn&3, cf=(e.insn>>13)&7;
        if((q==0 || q==2) && (cf==1 || cf==2 || cf==3 || cf==5 || cf==6 || cf==7)) {
          bool word=cf==2 || cf==6 || (cpu->get_xlen()==32 && (cf==3 || cf==7));
          width=word ? 4 : 8;
          rs=q==0 ? insn.rvc_rs1s() : 2;
          offset=q==0 ? (word ? insn.rvc_lw_imm() : insn.rvc_ld_imm()) :
            cf<4 ? (word ? insn.rvc_lwsp_imm() : insn.rvc_ldsp_imm()) :
                   (word ? insn.rvc_swsp_imm() : insn.rvc_sdsp_imm());
        }
      }
      uint64_t addr=(s->XPR[rs]+offset) & (cpu->get_xlen()==32 ? 0xffffffffULL : ~0ULL);
      if(width && addr%(cpu->get_xlen()/8)+width>cpu->get_xlen()/8)
        throw std::runtime_error("split bus/page access is outside scalar C2 comparison");
    }
    // Spike's load log stores addresses and sizes, but not raw load values.
    // Preserve the pre-store value of AMOs (including rd=x0); ordinary loads
    // can be observed after execution because this platform has inert MMIO.
    uint64_t amo_data=0; bool amo_valid=false;
    if((e.insn&0x7f)==0x2f) {
      auto addr=s->XPR[(e.insn>>15)&31]; auto width=(e.insn>>12)&7;
      try {
        if(width==2) { amo_data=cpu->get_mmu()->load<uint32_t>(addr); amo_valid=true; }
        if(width==3) { amo_data=cpu->get_mmu()->load<uint64_t>(addr); amo_valid=true; }
      } catch(...) {}
    }
    s->log_reg_write.clear(); s->log_mem_read.clear(); s->log_mem_write.clear();
    fflush(log); ftruncate(fileno(log),0); rewind(log);
    // An interrupt input the caller injects for this step only. The bit's earlier backdoor value is
    // kept and restored after the step: a pending bit that software set (an mip write) is reference
    // state and is never cleared here. The saved value is mip's own stored bits (the base-class
    // read), not mip.read(), which also ORs in state kept elsewhere (Spike holds software-written
    // SEIP in mvip): restoring that would leave the bit stuck after software clears it.
    // The caller injects only platform-declared inputs.
    uint64_t injected=0, prior=0;
    if(interrupt) {
      auto code=interrupt & ~(uint64_t(1)<<(cpu->get_xlen()-1));
      if(code>=64) throw std::runtime_error("invalid interrupt cause");
      injected=uint64_t(1)<<code;
      prior=s->mip->mip_or_mie_csr_t::read() & injected;
      s->mip->backdoor_write_with_mask(injected,injected);
    }
    // A hart may leave WFI at any time (WFI as a no-op is legal), so the reference
    // follows the core: the next trace record is the next instruction or an interrupt.
    cpu->clear_waiting_for_interrupt();
    cpu->step(1);
    if(cpu->halted()) throw std::runtime_error("debug-mode execution is not represented by C2");
    if(injected) s->mip->backdoor_write_with_mask(injected,prior);
    fflush(log); rewind(log);
    std::string diagnostic; char buf[1024];
    while(fgets(buf,sizeof(buf),log)) diagnostic+=buf;
    e.trap=diagnostic.find("exception ")!=std::string::npos;
    e.halted=cpu->is_waiting_for_interrupt();
    e.pc_next=s->pc;
    if(e.trap) {
      e.cause=(s->prv==1 ? s->scause : s->mcause)->read();
      e.tval=(s->prv==1 ? s->stval : s->mtval)->read();
      e.intr=e.cause>>(cpu->get_xlen()-1);
      auto c=e.cause & 0xff;
      e.mem_fault=!e.intr && (c==1||c==5||c==7||c==12||c==13||c==15);
    } else {
      for(auto& [key,value]:s->log_reg_write) if((key&15)==0 && (key>>4)!=0) {
        if(e.rd) throw std::runtime_error("multiple integer writes cannot be represented by C2");
        e.rd=key>>4; e.rd_wdata=value.v[0];
      }
      if(s->log_mem_read.size()>1 || s->log_mem_write.size()>1)
        throw std::runtime_error("multiple memory accesses cannot be represented by scalar C2");
      // Scalar C2 has one address and no bus transaction/partial-effect records.
      // Refuse split-word/page completion even if the reference can execute it.
      auto check_split = [&](const auto& accesses) {
        for(auto [addr,data,size]:accesses)
          if(size && addr/(cpu->get_xlen()/8)!=(addr+size-1)/(cpu->get_xlen()/8))
            throw std::runtime_error("split bus/page access is outside scalar C2 comparison");
      };
      check_split(s->log_mem_read); check_split(s->log_mem_write);
      auto reads=s->log_mem_read;
      auto writes=s->log_mem_write;
      for(auto [addr,data,size]:reads) {
        if(size>8) throw std::runtime_error("wide load requires an extended trace contract");
        e.mem_addr=addr; e.mem_rmask=(1ULL<<size)-1;
        if(amo_valid) e.mem_rdata=amo_data;
        else switch(size) {
          case 1: e.mem_rdata=cpu->get_mmu()->load<uint8_t>(addr); break;
          case 2: e.mem_rdata=cpu->get_mmu()->load<uint16_t>(addr); break;
          case 4: e.mem_rdata=cpu->get_mmu()->load<uint32_t>(addr); break;
          case 8: e.mem_rdata=cpu->get_mmu()->load<uint64_t>(addr); break;
          default: throw std::runtime_error("unsupported scalar load size");
        }
      }
      for(auto [addr,data,size]:writes) {
        if(size>8) throw std::runtime_error("wide store requires an extended trace contract");
        if(e.mem_rmask && e.mem_addr!=addr) throw std::runtime_error("split AMO address");
        e.mem_addr=addr; e.mem_wmask=(1ULL<<size)-1; e.mem_wdata=data;
      }
    }
    for(auto& [key,value]:s->log_reg_write) if((key&15)==1) {
      if(e.fd_valid) throw std::runtime_error("multiple FP writes are outside C2");
      e.fd_valid=1; e.fd=key>>4; e.fd_wdata=value.v[0];
    }
    e.fflags=s->fflags->read(); e.fcsr=e.fflags | (s->frm->read()<<5);
    for(size_t i=0;i<32;i++) e.regs[i]=s->XPR[i];
  }
};
static thread_local std::string error;
#ifndef RVW_SHIM_SOURCE_SHA256
#error "build with Cosim/build.sh: it defines RVW_SHIM_SOURCE_SHA256 (the hash of this file)"
#endif
#ifndef RVW_SHIM_BUILD_SHA256
#define RVW_SHIM_BUILD_SHA256 ""
#endif
extern "C" {
// ABI/behaviour version; rvw/src/rvw/cosim/spike.py (SHIM_VERSION) refuses any other value.
// 3: explicit privilege, misaligned and absent-PMP platform arguments.
unsigned rvw_shim_version() { return 5; }
// sha256 of the spike_shim.cc this library was built from; spike.py compares it with the source.
const char* rvw_shim_source_sha256() { return RVW_SHIM_SOURCE_SHA256; }
const char* rvw_shim_build_sha256() { return RVW_SHIM_BUILD_SHA256; }
const char* rvw_error() { return error.c_str(); }
void* rvw_create(const char* isa,const uint64_t* ram,size_t nr,const uint64_t* io,size_t ni,
                 uint64_t pc,unsigned pmp,const char* modes,int misaligned,int absent_pmp_zero) {
  try { return new Machine(isa,ram,nr,io,ni,pc,pmp,modes,misaligned,absent_pmp_zero); }
  catch(const std::exception& ex) { error=ex.what(); return nullptr; }
  catch(...) { error="Spike initialization failed"; return nullptr; }
}
void rvw_destroy(void* m) { delete static_cast<Machine*>(m); }
int rvw_write(void* m,uint64_t addr,const uint8_t* data,size_t n) {
  auto& machine=*static_cast<Machine*>(m);
  for(size_t i=0;i<n;i++) { char* p=machine.addr_to_mem(addr+i);
    if(!p) { error="ELF segment lies outside configured RAM"; return -1; } *p=data[i]; }
  return 0;
}
int rvw_step(void* m,Effect* out,uint64_t cause,uint64_t io_addr,uint64_t io_value,int inject) {
  try { auto& machine=*static_cast<Machine*>(m); machine.io_addr=io_addr;
    machine.io_value=io_value; machine.inject=inject; machine.step(*out,cause); return 0; }
  catch(const std::exception& ex) { error=ex.what(); return -1; }
  catch(...) { error="Spike raised an unsupported trap or debug trigger"; return -1; }
}
void rvw_sync_instret(void* m,uint64_t actual,uint64_t expected) {
  auto* s=static_cast<Machine*>(m)->cpu->get_state();
  s->minstret->write(s->minstret->read()+actual-expected);
  // Complete the debug-side CSR write now, not at the next instruction.
  // Spike suppresses one bump after an architectural counter write.
  s->minstret->bump(0);
}
// Platforms may write zero instead of the instruction bits to xtval on an
// illegal-instruction trap; overwrite the reference's trap value to match.
void rvw_set_trap_tval(void* m,uint64_t value) {
  auto* s=static_cast<Machine*>(m)->cpu->get_state();
  if(s->prv==PRV_M) s->mtval->write(value); else s->stval->write(value);
}
void rvw_set_mscratch(void* m,uint64_t value) {
  static_cast<Machine*>(m)->cpu->put_csr(CSR_MSCRATCH,value);
}
int rvw_read_csr(void* m,unsigned address,uint64_t* value) {
  try { *value=static_cast<Machine*>(m)->cpu->get_csr(address); return 0; }
  catch(...) { error="reference cannot observe requested CSR"; return -1; }
}
unsigned rvw_prv(void* m) { return static_cast<Machine*>(m)->cpu->get_state()->prv; }
void rvw_set_reg(void* m,unsigned rd,uint64_t value) {
  if(rd>0 && rd<32) static_cast<Machine*>(m)->cpu->get_state()->XPR.write(rd,value);
}
}
