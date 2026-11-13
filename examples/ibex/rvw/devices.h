// Single-hart simulation devices. Time advances once per harness cycle.
#pragma once
#include <cstdint>
#include <limits>

struct Devices {
  uint64_t time = 0, compare = std::numeric_limits<uint64_t>::max();
  uint32_t software = 0, external = 0;
  static bool mapped(uint32_t a) {
    return (a >= 0x02000000 && a < 0x0200c000) ||
           (a >= 0x0c000000 && a < 0x0c000008);
  }
  static void bytes(uint32_t &target, uint32_t value, unsigned enable) {
    for (unsigned b=0; b<4; ++b) if ((enable>>b)&1) {
      uint32_t mask=uint32_t(255)<<(8*b);
      target=(target&~mask)|(value&mask);
    }
  }
  uint32_t read(uint32_t address) const {
    switch (address & ~3u) {
      case 0x02000000: return software;
      case 0x02004000: return uint32_t(compare);
      case 0x02004004: return uint32_t(compare>>32);
      case 0x0200bff8: return uint32_t(time);
      case 0x0200bffc: return uint32_t(time>>32);
      case 0x0c000004: return external;
      default: return 0;
    }
  }
  void write(uint32_t address, uint32_t value, unsigned enable) {
    uint32_t lo, hi;
    switch (address & ~3u) {
      case 0x02000000:
        bytes(software,value,enable); software &= 1; break;
      case 0x02004000: case 0x02004004:
        lo=uint32_t(compare); hi=uint32_t(compare>>32);
        if (address&4) bytes(hi,value,enable); else bytes(lo,value,enable);
        compare=(uint64_t(hi)<<32)|lo; break;
      case 0x0200bff8: case 0x0200bffc:
        lo=uint32_t(time); hi=uint32_t(time>>32);
        if (address&4) bytes(hi,value,enable); else bytes(lo,value,enable);
        time=(uint64_t(hi)<<32)|lo; break;
      case 0x0c000004:
        // ACT4's simple interrupt generator: bit 31 selects set or clear.
        // This example implements word writes and the machine external bit.
        if (enable==15) {
          if (value&0x80000000u) external |= value&(1u<<11);
          else external &= ~(value&(1u<<11));
        }
        break;
      default: break;
    }
  }
  void tick() { ++time; }
  uint32_t levels() const {
    return (software ? 1u<<3 : 0) | (time>=compare ? 1u<<7 : 0) | external;
  }
};
