module coherent_fixture(coherent_if b);
  assign b.ready=1;
  assign b.observed_data=b.data^64'($test$plusargs("buggy"));
endmodule
