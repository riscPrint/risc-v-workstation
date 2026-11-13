#include "VFpuLaneUnit.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <string>
extern "C" uint64_t reference_case(unsigned,uint64_t,uint64_t,uint64_t,uint8_t,uint8_t*);
static uint64_t state=1;
static uint64_t random_bits(){state^=state<<13;state^=state>>7;state^=state<<17;return state;}
int main(int argc,char **argv){
  Verilated::commandArgs(argc,argv);
  VFpuLaneUnit dut;
  auto tick=[&](){dut.clk=0;dut.eval();dut.clk=1;dut.eval();};
  const uint64_t values32[]={0,0x80000000,1,0x007fffff,0x00800000,0x3f800000,0xbf800000,0x7f7fffff,0x7f800000,0xff800000,0x7fc00000,0x7f800001};
  const uint64_t values64[]={0,0x8000000000000000ull,1,0x000fffffffffffffull,0x0010000000000000ull,0x3ff0000000000000ull,0xbff0000000000000ull,0x7fefffffffffffffull,0x7ff0000000000000ull,0xfff0000000000000ull,0x7ff8000000000000ull,0x7ff0000000000001ull};
  const uint64_t *values=FP_WIDTH==32?values32:values64;
  const uint32_t instructions[]={0x002082d3,0x102082d3,0x182082d3,0x580082d3,0xc00082d3,0xd00082d3,0x182082c3,0x082082d3,0xc01082d3,0xd01082d3,0xc02082d3,0xd02082d3,0xc03082d3,0xd03082d3,0x420082d3,0x401082d3};
  auto check=[&](unsigned op,unsigned rm,uint64_t a,uint64_t b,uint64_t c,uint64_t expected,uint8_t flags){
    uint32_t insn=instructions[op] | (FP_WIDTH==64 && op<14 ? (1<<25):0);
    dut.reset=1;dut.start=0;dut.a=a;dut.b=b;dut.c=c;dut.instruction=insn;dut.rm=rm;tick();tick();tick();
    dut.reset=0;dut.start=1;tick();dut.start=0;
    unsigned cycles=0;
    while(!dut.done && cycles++<256)tick();
    if(!dut.done){std::fprintf(stderr,"completion bound width=%u op=%u rm=%u a=%llx b=%llx\n",FP_WIDTH,op,rm,(unsigned long long)a,(unsigned long long)b);std::exit(2);}
    if(dut.y!=expected || dut.flags!=flags){
      std::fprintf(stderr,"mismatch width=%u op=%u rm=%u a=%llx b=%llx c=%llx got=%llx/%x expected=%llx/%x\n",FP_WIDTH,op,rm,(unsigned long long)a,(unsigned long long)b,(unsigned long long)c,(unsigned long long)dut.y,unsigned(dut.flags),(unsigned long long)expected,unsigned(flags));std::exit(1);
    }
    return cycles;
  };
  unsigned checked=0;
  const unsigned operations=FP_WIDTH==32?10:16;
  const uint64_t integers[]={0,1,~0ull,0x7fffffff,0x80000000,0xffffffff,0x1000001,0x20000000000001ull,0x7fffffffffffffffull,0x8000000000000000ull,0xffffffff80000000ull,0x8000000000000001ull};
  for(unsigned op=0;op<operations;op++){
    unsigned max_cycles=0;
    for(unsigned rm=0;rm<5;rm++) for(unsigned i=0;i<1144;i++){
      uint64_t a=i<144?values[i/12]:random_bits();
      uint64_t b=i<144?values[i%12]:random_bits();
      uint64_t c=i<144?values[(i/12+i%12)%12]:random_bits();
      if((op==5 || op==9 || op==11 || op==13) && i<144)a=integers[i/12];
      if(op==14)a=0xffffffff00000000ull | (i<144?values32[i/12]:uint32_t(a));
      if(FP_WIDTH==32){a&=0xffffffff;b&=0xffffffff;c&=0xffffffff;}
      uint8_t flags=0;uint64_t expected=reference_case(op,a,b,c,rm,&flags);
      unsigned cycles=check(op,rm,a,b,c,expected,flags);
      if(cycles>max_cycles)max_cycles=cycles;
      checked++;
    }
    std::printf("{\"status\":\"match\",\"width\":%u,\"operation\":%u,\"vectors\":5720,\"rounding_modes\":5,\"seed\":1,\"max_cycles\":%u}\n",FP_WIDTH,op,max_cycles);std::fflush(stdout);
  }
  if(argc>1){
    std::ifstream input(argv[1]);
    if(!input){std::fprintf(stderr,"missing Spike vector file\n");return 2;}
    std::string line;unsigned count=0;
    while(std::getline(input,line)){
      unsigned op,rm,flags;uint64_t a,b,c,expected;
      std::istringstream row(line);
      if(!(row>>op>>rm>>std::hex>>a>>b>>c>>expected>>flags) || op>=operations || rm>=5 || flags>=32){std::fprintf(stderr,"invalid Spike vector\n");return 2;}
      uint8_t soft_flags=0;uint64_t soft=reference_case(op,a,b,c,rm,&soft_flags);
      if(soft!=expected || soft_flags!=flags){std::fprintf(stderr,"Spike/SoftFloat disagreement op=%u\n",op);return 3;}
      check(op,rm,a,b,c,expected,uint8_t(flags));count++;
    }
    if(!count)return 2;
    std::printf("{\"status\":\"match\",\"source\":\"Spike\",\"width\":%u,\"vectors\":%u}\n",FP_WIDTH,count);
  }
  return checked==operations*5720?0:3;
}
