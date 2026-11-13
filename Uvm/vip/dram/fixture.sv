// No native model is bundled. Projects must supply a model implementation.
module dram_bridge_fixture(dram_if b);
  assign b.ready=0;
endmodule
