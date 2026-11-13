// No native PCIe model is bundled. This inert bridge cannot claim a pass.
module pcie_bridge_fixture(pcie_if b);assign b.ready=0;endmodule
