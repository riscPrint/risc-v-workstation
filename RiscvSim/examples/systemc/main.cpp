#include "RVWTlmDevice.h"
#include "TlmMemory.h"
#include <tlm_utils/simple_initiator_socket.h>
#include <cassert>
#include <iostream>

struct Bridge : sc_core::sc_module {
  sc_core::sc_in<bool> clk,reset,req_valid,req_write;
  sc_core::sc_in<uint32_t> req_address,req_data;
  sc_core::sc_out<bool> rsp_valid;
  sc_core::sc_out<uint32_t> rsp_data;
  tlm_utils::simple_initiator_socket<Bridge> socket;
  SC_HAS_PROCESS(Bridge);
  Bridge(sc_core::sc_module_name n):sc_module(n),socket("socket") {SC_THREAD(run);}
  void run() {
    rsp_valid=false;rsp_data=0;
    while(true) {
      wait(clk.negedge_event());rsp_valid=false;
      if(reset.read() || !req_valid.read()) continue;
      uint32_t value=req_data.read();
      unsigned char data[4];
      for(unsigned i=0;i<4;++i)data[i]=(value>>(8*i))&255;
      tlm::tlm_generic_payload p;
      p.set_command(req_write.read()?tlm::TLM_WRITE_COMMAND:tlm::TLM_READ_COMMAND);
      p.set_address(req_address.read());p.set_data_ptr(data);
      p.set_data_length(4);p.set_streaming_width(4);
      p.set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);
      sc_core::sc_time delay=sc_core::SC_ZERO_TIME;
      socket->b_transport(p,delay);
      if(p.is_response_error()) SC_REPORT_FATAL("TLM","memory transaction failed");
      // One initiator, one outstanding transfer. The next rising edge consumes
      // the response. This example's 2 ns latency is less than the half period.
      wait(delay);
      value=0;for(unsigned i=0;i<4;++i)value|=uint32_t(data[i])<<(8*i);
      rsp_data=value;rsp_valid=true;
    }
  }
};
struct Reset : sc_core::sc_module {
  sc_core::sc_out<bool> reset;
  SC_CTOR(Reset) {SC_THREAD(run);}
  void run(){reset=true;wait(22,sc_core::SC_NS);reset=false;}
};
int sc_main(int argc,char** argv) {
  Verilated::commandArgs(argc,argv);
  using namespace sc_core;
  sc_clock clk("clk",10,SC_NS);
  sc_signal<bool> reset,request,write,response,done,error;
  sc_signal<uint32_t> address,data,result;
  RVWTlmDevice rtl("rtl");
  rtl.clk(clk);rtl.reset(reset);rtl.req_valid(request);rtl.req_write(write);
  rtl.req_address(address);rtl.req_data(data);rtl.rsp_valid(response);rtl.rsp_data(result);
  rtl.done(done);rtl.error(error);
  riscvsim::TlmMemory memory("memory",64,sc_time(2,SC_NS));
  Bridge bridge("bridge");bridge.clk(clk);bridge.reset(reset);
  bridge.req_valid(request);bridge.req_write(write);bridge.req_address(address);bridge.req_data(data);
  bridge.rsp_valid(response);bridge.rsp_data(result);bridge.socket.bind(memory.socket);
  Reset resetter("resetter");resetter.reset(reset);
  sc_start(100,SC_NS);
  assert(done.read() && !error.read());
  assert(memory.reads==1 && memory.writes==1);
  assert(memory.bytes[0]==0x78 && memory.bytes[3]==0x12);
  // Independent direct target checks: masked lane, annotated time and errors.
  tlm::tlm_generic_payload p;
  unsigned char bytes[4]={0xaa,0xbb,0xcc,0xdd}, mask[2]={255,0};
  p.set_command(tlm::TLM_WRITE_COMMAND);p.set_address(4);p.set_data_ptr(bytes);
  p.set_data_length(4);p.set_streaming_width(4);p.set_byte_enable_ptr(mask);p.set_byte_enable_length(2);
  sc_time delay=SC_ZERO_TIME;memory.transport(p,delay);
  assert(p.is_response_ok() && delay==sc_time(2,SC_NS));
  assert(memory.bytes[4]==0xaa && memory.bytes[5]==0 && memory.bytes[6]==0xcc && memory.bytes[7]==0);
  p.set_address(63);delay=SC_ZERO_TIME;memory.transport(p,delay);
  assert(p.get_response_status()==tlm::TLM_ADDRESS_ERROR_RESPONSE && delay==SC_ZERO_TIME);
  p.set_address(0);p.set_streaming_width(1);memory.transport(p,delay);
  assert(p.get_response_status()==tlm::TLM_BURST_ERROR_RESPONSE);
  std::cout<<"RVW_SYSTEMC_TLM_PASS rtl_writes=1 rtl_reads=1\n";
  return 0;
}
