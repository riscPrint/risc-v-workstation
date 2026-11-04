#include "VRtlTiny.h"
#include "verilated.h"
#include "verilated_cov.h"
#include <fstream>
int main(int argc, char **argv) {
  VerilatedContext context;
  VRtlTiny top{&context};
  std::ofstream out(argv[1]);
  out << "{\"schema\":\"rvw.rtl-samples/1\",\"plan_id\":\"" << argv[2]
      << "\",\"design\":\"" << argv[3] << "\"}\n";
  // Establish a known reset state before collection.
  top.clk = 0; top.reset = 1; top.go = 0; top.eval();
  top.clk = 1; top.eval();
  for (int cycle = 0; cycle < 24; ++cycle) {
    top.clk = 0; top.reset = cycle < 2; top.go = cycle % 2; top.eval();
    out << "{\"cycle\":" << cycle << ",\"values\":{\"TOP.clk\":0,\"TOP.reset\":"
        << int(top.reset) << ",\"TOP.state\":" << int(top.state) << "}}\n";
    top.clk = 1; top.eval();
  }
  out << "{\"event\":\"end\",\"complete\":true}\n";
  top.final();
  context.coveragep()->write(argv[4]);
}
