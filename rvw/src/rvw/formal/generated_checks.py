"""Optional project-bound safety monitors. No core signal names are inferred."""
NAMES = ('hpm', 'initialized_read', 'axi_lite')


def render(kind, width, entries):
    if kind not in NAMES or not 1 <= width <= 64 or not 1 <= entries <= 1024:
        raise ValueError('invalid generated check parameters')
    head = f'module rvw_{kind}(input clk, reset, '
    if kind == 'hpm':
        ports = f'''input [{width-1}:0] observed, events, write_data,
input inhibit, permitted, write_accepted, clear_pending, irq_enabled, pending, irq'''
        body = f'''reg [{width-1}:0] expected=0;
reg expected_pending=0;
wire [{width}:0] sum = {{1'b0,expected}} + {{1'b0,events}};
always @(posedge clk) begin
 if (reset) begin expected<=0; expected_pending<=0; end
 else begin
  assert(observed == expected);
  assert(pending == expected_pending);
  assert(irq == (expected_pending && irq_enabled));
  if (!inhibit && permitted) begin
   expected <= sum[{width-1}:0];
   if (sum[{width}]) expected_pending <= 1;
  end
  if (write_accepted) expected <= write_data;
  if (write_accepted) expected_pending <= expected_pending;
  if (clear_pending) expected_pending <= 0;
 end
end'''
    elif kind == 'initialized_read':
        ports = f'input read_used, input [{width-1}:0] read_mask, written_mask, required_mask'
        body = f'''reg [{width-1}:0] initialized=0;
always @(posedge clk) begin
 if(reset) initialized<=0;
 else begin
  if(read_used) assert((read_mask & required_mask & ~initialized) == 0);
  initialized <= initialized | written_mask;
 end
end'''
    elif kind == 'axi_lite':
        ports = '''input aw_fire, w_fire, b_fire, ar_fire, r_fire,
input [1:0] bresp, rresp, input awvalid, awready, wvalid, wready,
input bvalid, bready, arvalid, arready, rvalid, rready'''
        body = '''reg aw=0, wd=0, ar=0;
always @(posedge clk) begin
 if(reset) begin aw<=0; wd<=0; ar<=0; end
 else begin
  assert(aw_fire == (awvalid && awready));
  assert(w_fire == (wvalid && wready));
  assert(b_fire == (bvalid && bready));
  assert(ar_fire == (arvalid && arready));
  assert(r_fire == (rvalid && rready));
  assert(!(aw_fire && aw)); assert(!(w_fire && wd)); assert(!(ar_fire && ar));
  if(bvalid) begin assert(aw); assert(wd); assert(bresp != 1); end
  if(rvalid) begin assert(ar); assert(rresp != 1); end
  if(aw_fire) aw<=1; if(w_fire) wd<=1; if(ar_fire) ar<=1;
  if(b_fire) begin aw<=0; wd<=0; end
  if(r_fire) ar<=0;
 end
end'''
    return head + ports + ');\n' + body + '\nendmodule\n'
