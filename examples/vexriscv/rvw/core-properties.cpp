#include "VVexTop.h"
#include "verilated.h"
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <vector>

// One ordered response per accepted request. Stores have no response channel.
int main(int argc, char **argv) {
  if (argc != 3) return 2;
  Verilated::commandArgs(argc, argv);
  std::vector<uint8_t> ram(16 * 1024 * 1024, 0);
  std::ifstream input(argv[1], std::ios::binary);
  input.read(reinterpret_cast<char *>(ram.data()), ram.size());
  const uint32_t host = std::stoul(argv[2], nullptr, 0);
  auto word = [&](uint32_t address) {
    uint32_t value = 0;
    for (unsigned i = 0; i < 4; ++i)
      value |= uint32_t(ram.at(((address & ~3u) - 0x80000000u) + i)) << (8 * i);
    return value;
  };
  std::ofstream samples;
  if (const char *path = std::getenv("RVW_PROPERTY_TRACE")) samples.open(path);
  VVexTop dut;
  dut.reset = 1;
  dut.clk = 0;
  dut.timerInterrupt = dut.softwareInterrupt = dut.externalInterrupt = 0;
  dut.iBus_cmd_ready = dut.iBus_rsp_valid = dut.iBus_rsp_payload_error = 0;
  dut.iBus_rsp_payload_inst = 0;
  dut.dBus_cmd_ready = dut.dBus_rsp_ready = dut.dBus_rsp_error = 0;
  dut.dBus_rsp_data = 0;
  bool ipending = false, dpending = false, finished = false;
  uint32_t instruction = 0, data = 0, tohost = 0;
  unsigned cycles = 0, retirements = 0;
  try {
    for (; cycles < 200000 && !finished; ++cycles) {
      dut.clk = 0;
      dut.reset = cycles < 8;
      dut.iBus_cmd_ready = !ipending;
      dut.iBus_rsp_valid = ipending;
      dut.iBus_rsp_payload_inst = instruction;
      dut.dBus_cmd_ready = !dpending;
      dut.dBus_rsp_ready = dpending;
      dut.dBus_rsp_data = data;
      dut.eval();
      if (samples.is_open() && !dut.reset) {
        samples << "{";
        samples << "\"property_stage0_valid\":" << uint64_t(dut.property_stage0_valid);
        samples << ",\"property_stage0_fire\":" << uint64_t(dut.property_stage0_fire);
        samples << ",\"property_stage0_stuck\":" << uint64_t(dut.property_stage0_stuck);
        samples << ",\"property_stage0_pc\":" << uint64_t(dut.property_stage0_pc);
        samples << ",\"property_stage1_valid\":" << uint64_t(dut.property_stage1_valid);
        samples << ",\"property_stage1_fire\":" << uint64_t(dut.property_stage1_fire);
        samples << ",\"property_stage1_stuck\":" << uint64_t(dut.property_stage1_stuck);
        samples << ",\"property_stage1_pc\":" << uint64_t(dut.property_stage1_pc);
        samples << ",\"property_stage2_valid\":" << uint64_t(dut.property_stage2_valid);
        samples << ",\"property_stage2_fire\":" << uint64_t(dut.property_stage2_fire);
        samples << ",\"property_stage2_stuck\":" << uint64_t(dut.property_stage2_stuck);
        samples << ",\"property_stage2_pc\":" << uint64_t(dut.property_stage2_pc);
        samples << ",\"property_stage3_valid\":" << uint64_t(dut.property_stage3_valid);
        samples << ",\"property_stage3_fire\":" << uint64_t(dut.property_stage3_fire);
        samples << ",\"property_stage3_stuck\":" << uint64_t(dut.property_stage3_stuck);
        samples << ",\"property_stage3_pc\":" << uint64_t(dut.property_stage3_pc);
        samples << ",\"property_ibus_valid\":" << uint64_t(dut.property_ibus_valid);
        samples << ",\"property_ibus_ready\":" << uint64_t(dut.property_ibus_ready);
        samples << ",\"property_ibus_pc\":" << uint64_t(dut.property_ibus_pc);
        samples << ",\"property_dbus_valid\":" << uint64_t(dut.property_dbus_valid);
        samples << ",\"property_dbus_ready\":" << uint64_t(dut.property_dbus_ready);
        samples << ",\"property_dbus_address\":" << uint64_t(dut.property_dbus_address);
        samples << ",\"property_dbus_write\":" << uint64_t(dut.property_dbus_write);
        samples << ",\"property_retire\":" << uint64_t(dut.property_retire);
        samples << "}\n";
      }
      bool ia = !dut.reset && dut.iBus_cmd_valid && dut.iBus_cmd_ready;
      bool da = !dut.reset && dut.dBus_cmd_valid && dut.dBus_cmd_ready;
      uint32_t pc = dut.iBus_cmd_payload_pc;
      uint32_t address = dut.dBus_cmd_payload_address;
      uint32_t store = dut.dBus_cmd_payload_data;
      unsigned mask = dut.dBus_cmd_payload_mask;
      bool write = dut.dBus_cmd_payload_wr;
      retirements += !dut.reset && dut.rvfi_valid;
      dut.clk = 1;
      dut.eval();
      ipending = ia;
      dpending = da && !write;
      if (ia) instruction = word(pc);
      if (da && !write) data = word(address);
      if (da && write) {
        for (unsigned i = 0; i < 4; ++i)
          if (mask & (1u << i)) ram.at((address & ~3u) - 0x80000000u + i) = store >> (8 * i);
        if ((address & ~3u) == host) {
          tohost = word(host);
          finished = tohost != 0;
        }
      }
    }
  } catch (const std::out_of_range &) {
    std::cerr << "bus access outside example RAM\n";
  }
  dut.final();
  std::cout << "RVW_PROGRAM " << cycles << " " << retirements << " " << tohost << "\n";
  return finished && tohost == 1 ? 0 : 1;
}
