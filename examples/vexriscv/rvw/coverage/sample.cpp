#include "VVexTop.h"
#include "verilated.h"
#include "verilated_cov.h"
#include <fstream>
int main(int argc, char **argv) {
 VerilatedContext context; VVexTop top{&context}; std::ofstream out(argv[1]);
 out << "{\"schema\":\"rvw.rtl-samples/1\",\"plan_id\":\"" << argv[2] << "\",\"design\":\"" << argv[3] << "\"}\n";
 top.clk=0; top.reset=1; top.eval(); top.clk=1; top.eval();
 bool pending=false;
 for(int c=0;c<64;c++) {
  top.clk=0; top.reset=c<4; top.iBus_cmd_ready=(c%4)!=0;
  top.iBus_rsp_valid=pending; top.iBus_rsp_payload_error=0; top.iBus_rsp_payload_inst=0x13;
  top.dBus_cmd_ready=1; top.dBus_rsp_ready=0; top.dBus_rsp_error=0;
  top.timerInterrupt=0; top.externalInterrupt=0; top.externalInterruptS=0; top.softwareInterrupt=0;
  top.eval();
  out << "{\"cycle\":" << c << ",\"values\":{\"TOP.clk\":0,\"TOP.reset\":" << int(top.reset)
      << ",\"TOP.iBus_cmd_valid\":" << int(top.iBus_cmd_valid) << ",\"TOP.iBus_cmd_ready\":" << int(top.iBus_cmd_ready)
      << ",\"TOP.iBus_rsp_valid\":" << int(top.iBus_rsp_valid) << "}}\n";
  pending=!top.reset && top.iBus_cmd_valid && top.iBus_cmd_ready;
  top.clk=1; top.eval();
 }
 out << "{\"event\":\"end\",\"complete\":true}\n";
 top.final(); context.coveragep()->write(argv[4]);
}
