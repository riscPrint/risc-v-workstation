#include "VFpuSqrtHarness.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
extern "C" uint64_t reference(uint64_t,uint64_t,uint64_t,uint8_t,uint8_t*);
static uint64_t state=1;
static uint64_t random_bits(){state^=state<<13;state^=state>>7;state^=state<<17;return state;}
int main(int argc,char **argv){
  Verilated::commandArgs(argc,argv);
  VFpuSqrtHarness dut;
  auto tick=[&](){dut.clk=0;dut.eval();dut.clk=1;dut.eval();};
  constexpr unsigned p=FP_WIDTH==32?23:52;
  constexpr unsigned e=FP_WIDTH==32?8:11;
  constexpr uint64_t mask=(UINT64_C(1)<<p)-1;
  constexpr unsigned max_exp=(1u<<e)-1;
  unsigned checked=0;
  const unsigned edges[]={1,2,3,max_exp/2,max_exp/2+1,max_exp-2,max_exp-1,1,max_exp-1,2};
  for(unsigned rm=0;rm<5;rm++) for(unsigned i=0;i<10000;i++){
    // Positive normal values only. Include exponent and fraction boundaries.
    unsigned exponent=i<10 ? edges[i] : 1+random_bits()%(max_exp-1);
    uint64_t fraction=i<10 ? ((i&1)?mask:0) : random_bits()&mask;
    uint64_t a=(uint64_t(exponent)<<p)|fraction;
    dut.reset=1;dut.io_start=0;dut.io_a=a;dut.io_rm=rm;tick();tick();
    dut.reset=0;dut.io_start=1;tick();dut.io_start=0;
    unsigned cycles=0;
    while(!dut.io_done && cycles++<p+8)tick();
    if(!dut.io_done){std::fprintf(stderr,"completion bound\n");return 2;}
    uint8_t flags=0;uint64_t expected=reference(a,0,0,rm,&flags);
    if(dut.io_y!=expected || dut.io_flags!=flags){
      std::fprintf(stderr,"mismatch width=%u rm=%u a=%llx got=%llx/%x expected=%llx/%x\n",FP_WIDTH,rm,(unsigned long long)a,(unsigned long long)dut.io_y,unsigned(dut.io_flags),(unsigned long long)expected,unsigned(flags));return 1;
    }
    checked++;
  }
  std::printf("{\"status\":\"match\",\"width\":%u,\"vectors\":%u,\"domain\":\"positive normal\",\"rounding_modes\":5,\"seed\":1}\n",FP_WIDTH,checked);
}
