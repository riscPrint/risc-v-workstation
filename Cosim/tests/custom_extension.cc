// Independent example: custom-0 adds literal 7 to rs1 and writes rd.
#include <riscv/extension.h>
static reg_t add7(processor_t* p, insn_t insn, reg_t pc) {
  auto value = p->get_state()->XPR[insn.rs1()] + 7;
  p->get_state()->XPR.write(insn.rd(), value);
  if (insn.rd()) p->get_state()->log_reg_write[insn.rd()<<4] = {value, 0};
  return pc + 4;
}
class example_t : public extension_t {
public:
  const char* name() const override { return "rvw_example"; }
  std::vector<insn_desc_t> get_instructions(const processor_t&) override {
    return {{0x0b, 0x707f, add7, add7, add7, add7, add7, add7, add7, add7}};
  }
  std::vector<disasm_insn_t*> get_disasms(const processor_t*) override { return {}; }
};
REGISTER_EXTENSION(rvw_example, []() { return new example_t; })
