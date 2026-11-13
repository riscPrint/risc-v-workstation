// No model. The zero initialization is never a valid analog observation.
module rnm_stub_fixture(rnm_if b);initial begin b.value=0.0;b.valid=0;b.known=0;end endmodule
