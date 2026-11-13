// No native packet model is bundled. An absent backend never accepts packets.
module ethernet_bridge_fixture(ethernet_if b);assign b.ready=0;endmodule
