#include "Vtiny.h"
#include "verilated.h"
#include "verilated_cov.h"
#include <cstdlib>
int main(int argc, char **argv) {
    VerilatedContext context;
    context.commandArgs(argc, argv);
    Vtiny top{&context};
    for (int i = 0; i < 8; ++i) {
        top.a = i;
        top.choose = std::atoi(argv[1]);
        top.clk = 0;
        top.eval();
        top.clk = 1;
        top.eval();
    }
    top.final();
    context.coveragep()->write(argv[2]);
}
