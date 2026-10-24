#include "VCoverageTiny.h"
#include "verilated.h"
#include "verilated_cov.h"
int main(int argc, char **argv) {
    VerilatedContext context;
    context.commandArgs(argc, argv);
    VCoverageTiny top{&context};
    for (int i = 0; i < 20; ++i) {
        top.clk = 0;
        top.reset = i < 2;
        top.io_a = i & 15;
        top.io_choose = i & 1;
        top.eval();
        top.clk = 1;
        top.eval();
    }
    top.final();
    context.coveragep()->write(argv[1]);
}
