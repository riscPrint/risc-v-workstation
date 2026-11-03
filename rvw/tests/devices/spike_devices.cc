// Native oracle: use Spike devices directly, independently of the Python models.
#include <riscv/devices.h>
#include <riscv/processor.h>
#include <riscv/simif.h>
#include <iostream>
#include <memory>
#include <sstream>
struct Machine : simif_t {
  cfg_t cfg;
  std::map<size_t, processor_t*> harts;
  std::vector<std::unique_ptr<processor_t>> cpus;
  Machine() {
    for (size_t i=0;i<2;i++) {
      cpus.emplace_back(new processor_t("rv64imac", "MSU", &cfg, this, i, false, nullptr, std::cerr));
      harts[i]=cpus.back().get();
    }
  }
  char* addr_to_mem(reg_t) override { return nullptr; }
  bool mmio_load(reg_t,size_t,uint8_t*) override { return false; }
  bool mmio_store(reg_t,size_t,const uint8_t*) override { return false; }
  void proc_reset(unsigned) override {}
  const cfg_t& get_cfg() const override { return cfg; }
  const std::map<size_t,processor_t*>& get_harts() const override { return harts; }
  const char* get_symbol(uint64_t) override { return nullptr; }
};
int main(int argc,char** argv) {
  Machine m;
  std::unique_ptr<abstract_device_t> dev;
  if (argc == 2 && std::string(argv[1]) == "plic") dev.reset(new plic_t(&m,63));
  else dev.reset(new clint_t(&m,1000000,false));
  std::string line;
  while(std::getline(std::cin,line)) {
    std::istringstream in(line); char op; uint64_t a=0,v=0,n=4; in>>op>>a>>v>>n;
    uint8_t bytes[8]={}; bool ok=true; uint64_t result=0;
    if(n>8) return 2;
    if(op=='r') { ok=dev->load(a,n,bytes); for(size_t i=0;i<n;i++) result|=uint64_t(bytes[i])<<(8*i); }
    else if(op=='w') { for(size_t i=0;i<n;i++) bytes[i]=v>>(8*i); ok=dev->store(a,n,bytes); }
    else if(op=='l') dynamic_cast<plic_t&>(*dev).set_interrupt_level(a,v);
    else if(op=='t') dev->tick(a);
    else return 2;
    std::cout<<ok<<" "<<result;
    for(auto& cpu:m.cpus) std::cout<<" "<<cpu->get_state()->mip->read();
    std::cout<<std::endl;
  }
}
