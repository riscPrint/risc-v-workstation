// Additive deterministic replay sessions. The existing Spike ABI is supplied by pointer.
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <memory>
#include <string>
#include <vector>
#include <stdexcept>

struct Effect {
  uint64_t pc,pc_next,insn,mode,rd,rd_wdata;
  uint64_t mem_addr,mem_rmask,mem_wmask,mem_rdata,mem_wdata;
  uint64_t trap,intr,cause,tval,mem_fault,halted;
  uint64_t fd_valid,fd,fd_wdata,fflags,fcsr;
  uint64_t regs[32]; char disasm[256];
};
struct Api {
  void* (*create)(const char*,const uint64_t*,size_t,const uint64_t*,size_t,uint64_t,unsigned,uint64_t,const char*,int,int);
  void (*destroy)(void*);
  int (*write)(void*,uint64_t,const uint8_t*,size_t);
  int (*step)(void*,Effect*,uint64_t,uint64_t,uint64_t,int);
  int (*redirect)(void*,uint64_t);
  const char* (*error)();
};
struct Initial {
  Api api; std::string isa,modes; std::vector<uint64_t> ram,io;
  uint64_t pc,grain; unsigned pmp; int misaligned,absent_pmp_zero;
};
struct Action {
  enum Kind { WRITE, STEP, REDIRECT } kind;
  uint64_t a=0,b=0,c=0,expected=0; int inject=0; std::vector<uint8_t> bytes;
};
static thread_local std::string replay_error;
struct Session {
  Initial initial; void* machine=nullptr; bool poisoned=false; std::shared_ptr<std::vector<Action>> history=std::make_shared<std::vector<Action>>();
  explicit Session(const Initial& init):initial(init) {
    auto& i=initial;
    machine=i.api.create(i.isa.c_str(),i.ram.data(),i.ram.size()/2,i.io.data(),i.io.size()/2,
                         i.pc,i.pmp,i.grain,i.modes.c_str(),i.misaligned,i.absent_pmp_zero);
    if(!machine) throw std::runtime_error(i.api.error());
  }
  ~Session() { if(machine) initial.api.destroy(machine); }
  int apply(const Action& a,Effect* effect=nullptr) {
    if(poisoned) { replay_error="replay session is poisoned; restore a prior checkpoint";return -1; }
    Effect ignored{}; int status=0;
    if(a.kind==Action::WRITE) status=initial.api.write(machine,a.a,a.bytes.data(),a.bytes.size());
    else if(a.kind==Action::REDIRECT) status=initial.api.redirect(machine,a.a);
    else status=initial.api.step(machine,effect?effect:&ignored,a.a,a.b,a.c,a.inject);
    if(status) { poisoned=true;replay_error=initial.api.error(); }
    return status;
  }
};
struct Snapshot { Initial initial; std::shared_ptr<std::vector<Action>> history; size_t size; };
static uint64_t effect_hash(const Effect& effect) {
  uint64_t hash=14695981039346656037ULL;
  auto* data=reinterpret_cast<const unsigned char*>(&effect);
  for(size_t i=0;i<sizeof(effect);i++) hash=(hash^data[i])*1099511628211ULL;
  return hash;
}

extern "C" {
unsigned rvw_replay_abi() { return 1; }
size_t rvw_replay_effect_size() { return sizeof(Effect); }
const char* rvw_replay_error() { return replay_error.c_str(); }
void* rvw_replay_create(const Api* api,const char* isa,const uint64_t* ram,size_t nr,
                       const uint64_t* io,size_t ni,uint64_t pc,unsigned pmp,uint64_t grain,
                       const char* modes,int misaligned,int absent_pmp_zero) {
  try {
    if(!api || !api->create || !api->destroy || !api->write || !api->step || !api->redirect || !api->error)
      throw std::runtime_error("incomplete Spike API table");
    Initial init{*api,isa,modes,{}, {},pc,grain,pmp,misaligned,absent_pmp_zero};
    if(nr) init.ram.assign(ram,ram+2*nr);
    if(ni) init.io.assign(io,io+2*ni);
    return new Session(init);
  } catch(const std::exception& e) { replay_error=e.what();return nullptr; }
}
void rvw_replay_destroy(void* handle) { delete static_cast<Session*>(handle); }
int rvw_replay_write(void* handle,uint64_t address,const uint8_t* data,size_t n) {
  try {
    auto& s=*static_cast<Session*>(handle);Action a; a.kind=Action::WRITE;a.a=address;
    if(n) a.bytes.assign(data,data+n);
    s.history->push_back(std::move(a));
    return s.apply(s.history->back());
  } catch(const std::exception& e) { replay_error=e.what();return -1; }
}
int rvw_replay_step(void* handle,Effect* effect,uint64_t cause,uint64_t address,uint64_t value,int inject) {
  try {
    auto& s=*static_cast<Session*>(handle);Action a;a.kind=Action::STEP;
    a.a=cause;a.b=address;a.c=value;a.inject=inject;
    s.history->push_back(std::move(a));
    int status=s.apply(s.history->back(),effect);
    if(!status) s.history->back().expected=effect_hash(*effect);
    return status;
  } catch(const std::exception& e) { replay_error=e.what();return -1; }
}
int rvw_replay_redirect(void* handle,uint64_t pc) {
  try {
    auto& s=*static_cast<Session*>(handle);Action a;a.kind=Action::REDIRECT;a.a=pc;
    s.history->push_back(std::move(a));
    return s.apply(s.history->back());
  } catch(const std::exception& e) { replay_error=e.what();return -1; }
}
void* rvw_replay_checkpoint(void* handle) {
  try {
    auto& s=*static_cast<Session*>(handle);
    if(s.poisoned) throw std::runtime_error("cannot checkpoint a poisoned replay session");
    return new Snapshot{s.initial,s.history,s.history->size()};
  } catch(const std::exception& e) { replay_error=e.what();return nullptr; }
}
void rvw_replay_checkpoint_free(void* handle) { delete static_cast<Snapshot*>(handle); }
void* rvw_replay_restore(void* checkpoint) {
  try {
    auto& saved=*static_cast<Snapshot*>(checkpoint);
    auto s=std::make_unique<Session>(saved.initial);
    for(size_t i=0;i<saved.size;i++) {
      const auto& a=(*saved.history)[i];Effect observed{};
      if(s->apply(a,&observed)) return nullptr;
      if(a.kind==Action::STEP && effect_hash(observed)!=a.expected) {
        replay_error="functional replay effects differ from checkpoint history";return nullptr;
      }
    }
    s->history->assign(saved.history->begin(),saved.history->begin()+saved.size);
    return s.release();
  } catch(const std::exception& e) { replay_error=e.what();return nullptr; }
}
}
