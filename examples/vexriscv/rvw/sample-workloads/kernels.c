/* Bare-metal, deterministic sampling workloads. No counter or device reads. */
#include <stdint.h>
#ifndef SIZE
#define SIZE 1024
#endif
#ifndef ROUNDS
#define ROUNDS 10
#endif
static uint32_t values[SIZE];
static uint8_t input[SIZE], packed[2*SIZE];
volatile uint32_t checksum;

static void sift(unsigned root, unsigned end) {
  for (;;) {
    unsigned child = 2*root+1;
    if (child >= end) return;
    if (child+1 < end && values[child] < values[child+1]) ++child;
    if (values[root] >= values[child]) return;
    uint32_t v=values[root]; values[root]=values[child]; values[child]=v;
    root=child;
  }
}

static int sort(unsigned round) {
  uint32_t state=round+1;
  for (unsigned i=0;i<SIZE;++i) values[i]=state=1664525*state+1013904223;
  for (unsigned i=SIZE/2;i>0;--i) sift(i-1,SIZE);
  for (unsigned end=SIZE;end>1;--end) {
    uint32_t v=values[0]; values[0]=values[end-1]; values[end-1]=v;
    sift(0,end-1);
  }
  for (unsigned i=1;i<SIZE;++i) if (values[i-1]>values[i]) return 0;
  checksum ^= values[SIZE/2];
  return 1;
}

static int compression(unsigned round) {
  for (unsigned i=0;i<SIZE;++i) input[i]=(uint8_t)((i/(3+round%13))%23);
  unsigned used=0;
  for (unsigned i=0;i<SIZE;) {
    uint8_t value=input[i]; unsigned run=1;
    while (i+run<SIZE && run<255 && input[i+run]==value) ++run;
    packed[used++]=(uint8_t)run; packed[used++]=value; i+=run;
  }
  unsigned pos=0;
  for (unsigned i=0;i<used;i+=2) {
    for (unsigned n=0;n<packed[i];++n) {
      if (pos>=SIZE || input[pos++]!=packed[i+1]) return 0;
    }
  }
  checksum += used;
  return pos==SIZE;
}

int main(void) {
  for (unsigned r=0;r<ROUNDS;++r) {
#ifdef COMPRESSION
    if (!compression(r)) return 3;
#else
    if (!sort(r)) return 3;
#endif
  }
  return 1;
}
