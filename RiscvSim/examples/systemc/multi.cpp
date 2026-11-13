#include "TlmMemory.h"
#include <tlm_utils/simple_initiator_socket.h>
#include <cassert>
#include <iostream>

struct Initiator : sc_core::sc_module {
  tlm_utils::simple_initiator_socket<Initiator> socket;
  int id;
  bool done=false;
  SC_HAS_PROCESS(Initiator);
  Initiator(sc_core::sc_module_name name, int i):sc_module(name),socket("socket"),id(i) {SC_THREAD(run);}
  void access(bool write, uint64_t address, unsigned char& data) {
    tlm::tlm_generic_payload p;
    p.set_command(write ? tlm::TLM_WRITE_COMMAND : tlm::TLM_READ_COMMAND);
    p.set_address(address);p.set_data_ptr(&data);p.set_data_length(1);p.set_streaming_width(1);
    sc_core::sc_time delay=sc_core::SC_ZERO_TIME;
    socket->b_transport(p,delay);
    assert(p.is_response_ok() && delay==sc_core::sc_time(2,sc_core::SC_NS));
    wait(delay);
  }
  void run() {
    // Stagger calls to make the shared-address order explicit.
    wait(id ? 3 : 1, sc_core::SC_NS);
    unsigned char value=id ? 0xbb : 0xaa;
    access(true,0,value);
    // Both writes finish by 5 ns. Each reader must see initiator 1's write.
    wait(10-sc_core::sc_time_stamp().to_double()/sc_core::sc_time(1,sc_core::SC_NS).to_double(),sc_core::SC_NS);
    value=0;access(false,0,value);assert(value==0xbb);
    value=0x10+id;access(true,8+id,value);
    value=0;access(false,8+id,value);assert(value==0x10+id);
    done=true;
  }
};
int sc_main(int, char**) {
  riscvsim::TlmMemory memory("memory",64,sc_core::sc_time(2,sc_core::SC_NS));
  Initiator a("a",0),b("b",1);
  a.socket.bind(memory.socket);b.socket.bind(memory.socket);
  sc_core::sc_start(30,sc_core::SC_NS);
  assert(a.done && b.done && memory.bytes[0]==0xbb);
  assert(memory.reads==4 && memory.writes==4);
  assert(memory.initiatorReads.size()==2 && memory.initiatorWrites.size()==2);
  for(int id=0;id<2;++id)assert(memory.initiatorReads[id]==2 && memory.initiatorWrites[id]==2);
  std::cout << "RVW_TLM_MULTI_PASS initiators=2 reads=4 writes=4\n";
  return 0;
}
