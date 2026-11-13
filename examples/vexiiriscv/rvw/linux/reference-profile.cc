// Project reference profile: ParamSimple.physicalWidth=32, eight PMP entries.
// Keep Spike's PMP objects and permission checks. Constrain their CSR writes
// and reads to the implemented physical address width. MTOPI is implemented
// unconditionally by this core profile, without the complete Smaia extension.
// No DUT values enter this reference configuration.
#include <riscv/extension.h>
#include <riscv/csrs.h>
#include <riscv/trap.h>

class pmp32_csr final : public csr_t {
  csr_t_p original;
  static constexpr reg_t mask = (reg_t(1) << 30)-1;
 public:
  pmp32_csr(processor_t& cpu, reg_t address, csr_t_p prior)
    : csr_t(&cpu,address), original(prior) {}
  reg_t read() const noexcept override { return original->read() & mask; }
  void verify_permissions(insn_t insn, bool write) const override {
    original->verify_permissions(insn,write);
  }
 protected:
  bool unlogged_write(reg_t value) noexcept override {
    original->write(value & mask);
    return false; // The original CSR logged its own write.
  }
};

class mtopi_csr final : public csr_t {
 public:
  explicit mtopi_csr(processor_t& cpu) : csr_t(&cpu,0xfb0) {}
  reg_t read() const noexcept override {
    auto bits = state->csrmap.at(0x344)->read() & state->mie->read() & ~state->mideleg->read();
    for(auto code : {11,3,7,9,1,5})
      if(bits & (reg_t(1)<<code)) return (reg_t(code)<<16) | 1;
    return 0;
  }
 protected:
  bool unlogged_write(reg_t) noexcept override { return false; }
};

class absent_trigger_csr final : public csr_t {
 public:
  absent_trigger_csr(processor_t& cpu, reg_t address) : csr_t(&cpu,address) {}
  void verify_permissions(insn_t insn, bool) const override {
    throw trap_illegal_instruction(insn.bits());
  }
  reg_t read() const noexcept override { return 0; }
 protected:
  bool unlogged_write(reg_t) noexcept override { return false; }
};

class linux_extension final : public extension_t {
 public:
  const char* name() const override { return "rvw_vexii_linux"; }
  void reset(processor_t& cpu) override {
    cpu.set_mmu_capability(IMPL_MMU_SV39);
    cpu.set_impl(IMPL_MMU_SV48,false);
    cpu.set_impl(IMPL_MMU_SV57,false);
  }
  std::vector<insn_desc_t> get_instructions(const processor_t&) override { return {}; }
  std::vector<disasm_insn_t*> get_disasms(const processor_t*) override { return {}; }
  std::vector<csr_t_p> get_csrs(processor_t& cpu) const override {
    std::vector<csr_t_p> result;
    for(unsigned a=0x3b0; a<0x3b8; a++)
      result.push_back(std::make_shared<pmp32_csr>(cpu,a,cpu.get_state()->csrmap.at(a)));
    result.push_back(std::make_shared<mtopi_csr>(cpu));
    // The selected ParamSimple profile has no TriggerPlugin. Spike otherwise
    // supplies trigger CSRs which make OpenSBI detect a different platform.
    for(auto a : {0x7a0,0x7a1,0x7a2,0x7a3,0x7a4,0x7a5,0x7a8,0x5a8})
      result.push_back(std::make_shared<absent_trigger_csr>(cpu,a));
    return result;
  }
};
REGISTER_EXTENSION(rvw_vexii_linux, []() { return new linux_extension; })
