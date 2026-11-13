#pragma once
#include <systemc>
#include <tlm>
#include <tlm_utils/multi_passthrough_target_socket.h>
#include <map>
#include <cstdint>
#include <vector>

namespace riscvsim {
// Blocking memory shared by SystemC initiators. The caller consumes annotated delay.
// The target neither waits nor keeps payload pointers. No DMI or atomics.
struct TlmMemory : sc_core::sc_module {
  tlm_utils::multi_passthrough_target_socket<TlmMemory> socket;
  std::vector<unsigned char> bytes;
  sc_core::sc_time latency;
  uint64_t reads=0, writes=0;
  std::map<int, uint64_t> initiatorReads, initiatorWrites;
  TlmMemory(sc_core::sc_module_name name, size_t size, sc_core::sc_time delay)
      : sc_module(name), socket("socket"), bytes(size, 0), latency(delay) {
    socket.register_b_transport(this, &TlmMemory::transportFrom);
  }
  void transportFrom(int id, tlm::tlm_generic_payload& p, sc_core::sc_time& delay) {
    transport(p, delay);
    if (p.is_response_ok()) {
      if (p.is_read()) ++initiatorReads[id]; else ++initiatorWrites[id];
    }
  }
  void transport(tlm::tlm_generic_payload& p, sc_core::sc_time& delay) {
    p.set_dmi_allowed(false);
    const auto address=p.get_address();
    const auto size=p.get_data_length();
    const auto enable=p.get_byte_enable_ptr();
    const auto enables=p.get_byte_enable_length();
    if (!p.is_read() && !p.is_write()) {p.set_response_status(tlm::TLM_COMMAND_ERROR_RESPONSE);return;}
    if (!size || !p.get_data_ptr() || address>bytes.size() || size>bytes.size()-address) {
      p.set_response_status(tlm::TLM_ADDRESS_ERROR_RESPONSE);return;
    }
    if (p.get_streaming_width()<size) {p.set_response_status(tlm::TLM_BURST_ERROR_RESPONSE);return;}
    if (enable) {
      if (!enables) {p.set_response_status(tlm::TLM_BYTE_ENABLE_ERROR_RESPONSE);return;}
      for (unsigned i=0;i<enables;++i)
        if (enable[i]!=0 && enable[i]!=255) {p.set_response_status(tlm::TLM_BYTE_ENABLE_ERROR_RESPONSE);return;}
    }
    for (unsigned i=0;i<size;++i) {
      if (enable && !enable[i%enables]) continue;
      if (p.is_read()) p.get_data_ptr()[i]=bytes[address+i];
      else bytes[address+i]=p.get_data_ptr()[i];
    }
    if (p.is_read()) ++reads; else ++writes;
    delay+=latency;
    p.set_response_status(tlm::TLM_OK_RESPONSE);
  }
};
}
