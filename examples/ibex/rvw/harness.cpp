// One-cycle responses. Each grant samples one request at the rising edge.
#include "Vibex_top.h"
#include "verilated.h"
#include "verilated_cov.h"
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <vector>
#include <string>

int main(int argc, char **argv) {
  if (argc != 5) return 2;
  VerilatedContext context;
  Vibex_top d{&context};
  std::ifstream input(argv[1], std::ios::binary);
  std::vector<uint8_t> mem(0x100000);
  input.read(reinterpret_cast<char*>(mem.data()), mem.size());
  if (!input) return 2;
  uint32_t tohost=std::stoul(argv[2]);
  uint64_t limit=std::stoull(argv[3]), cycles=0, instret=0;
  std::string out=argv[4], status="timeout";
  auto valid=[&](uint32_t a) {return a>=0x80000000u && a<0x80100000u;};
  auto read=[&](uint32_t a) {uint32_t v=0; a &= ~3u; if(valid(a)) for(int b=0;b<4;b++) v|=uint32_t(mem[a-0x80000000u+b])<<(8*b); return v;};
  std::ofstream trace(out+"/rvfi.jsonl");
  trace << "{\"schema\":\"rvw.rvfi/1\",\"core\":\"ibex\",\"config\":\"default\",\"xlen\":32,\"isa\":\"rv32imc_zicsr_zifencei\"}\n";
  d.boot_addr_i=0x80000000; d.hart_id_i=0; d.fetch_enable_i=5;
  d.test_en_i=1; d.scan_rst_ni=1; d.rst_ni=0;
  d.clk_i=0; d.eval();
  for(int i=0;i<8;i++) { d.clk_i=1; d.eval(); context.timeInc(1); d.clk_i=0; d.eval(); context.timeInc(1); }
  d.rst_ni=1;
  bool ip=false,dp=false,ie=false,de=false; uint32_t ir=0,dr=0,finish=0;
  for(cycles=1;cycles<=limit;cycles++) {
    d.clk_i=0;
    d.instr_rvalid_i=ip; d.instr_rdata_i=ir; d.instr_err_i=ie;
    d.data_rvalid_i=dp; d.data_rdata_i=dr; d.data_err_i=de;
    d.instr_gnt_i=1; d.data_gnt_i=1; d.eval();
    ip=d.instr_req_o; dp=d.data_req_o;
    ir=read(d.instr_addr_o); ie=ip&&!valid(d.instr_addr_o);
    dr=read(d.data_addr_o); de=dp&&!valid(d.data_addr_o);
    if(dp && d.data_we_o && valid(d.data_addr_o)) {
      auto a=d.data_addr_o & ~3u;
      for(int b=0;b<4;b++) if((d.data_be_o>>b)&1) mem[a-0x80000000u+b]=d.data_wdata_o>>(8*b);
      if(a==tohost) finish=read(a);
    }
    d.clk_i=1; d.eval(); context.timeInc(1);
    if(d.rvfi_valid) {
      instret++;
      if(d.rvfi_order != instret) return 2;
      trace << "{\"order\":" << (d.rvfi_order-1) << ",\"cycle\":" << cycles;
#define NUM(key,field) trace << ",\"" key "\":" << unsigned(d.field)
#define HEX(key,field) trace << ",\"" key "\":\"0x" << std::hex << uint32_t(d.field) << std::dec << "\""
      HEX("pc",rvfi_pc_rdata); HEX("pc_next",rvfi_pc_wdata); HEX("insn",rvfi_insn);
      NUM("mode",rvfi_mode);
      trace << std::boolalpha << ",\"trap\":" << bool(d.rvfi_trap)
            << ",\"intr\":" << bool(d.rvfi_intr) << ",\"halt\":" << bool(d.rvfi_halt);
      NUM("rs1",rvfi_rs1_addr); NUM("rs2",rvfi_rs2_addr); NUM("rd",rvfi_rd_addr);
      HEX("rs1_rdata",rvfi_rs1_rdata); HEX("rs2_rdata",rvfi_rs2_rdata); HEX("rd_wdata",rvfi_rd_wdata);
      uint32_t insn=d.rvfi_insn;
      bool compressed=(insn&3)!=3;
      unsigned quadrant=insn&3, funct3=(insn>>13)&7;
      bool load=compressed ? ((quadrant==0 || quadrant==2) && funct3==2) : (insn&127)==3;
      bool store=compressed ? ((quadrant==0 || quadrant==2) && funct3==6) : (insn&127)==35;
      // Upstream leaves masks live for non-memory instructions. Preserve raw values.
      NUM("ibex_raw_mem_rmask",rvfi_mem_rmask); NUM("ibex_raw_mem_wmask",rvfi_mem_wmask);
      HEX("mem_addr",rvfi_mem_addr);
      trace << ",\"mem_rmask\":" << (load ? unsigned(d.rvfi_mem_rmask) : 0)
            << ",\"mem_wmask\":" << (store ? unsigned(d.rvfi_mem_wmask) : 0);
      HEX("mem_rdata",rvfi_mem_rdata); HEX("mem_wdata",rvfi_mem_wdata);
      trace << ",\"mem_fault\":false}\n";
      // End only when the tohost store retires, so the trace includes completion.
      if(finish && d.rvfi_mem_wmask && (d.rvfi_mem_addr & ~3u)==tohost) {
        status=finish==1 ? "pass" : "fail"; break;
      }
    }
    d.clk_i=0; d.eval(); context.timeInc(1);
  }
  d.final();
  trace << "{\"event\":\"end\",\"cycle\":" << cycles << ",\"status\":\"" << status << "\"}\n";
  std::ofstream result(out+"/native.json");
  result << "{\"status\":\"" << status << "\",\"cycles\":" << cycles << ",\"instret\":" << instret << ",\"fail_code\":" << (finish>>1) << "}";
  context.coveragep()->write((out+"/coverage.dat").c_str());
}
