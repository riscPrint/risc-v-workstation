"""Sampled low-power monitors. Bind them to an always-on observation clock."""
NAMES = ('clock_gate', 'isolation', 'retention', 'test_isolation')


def render(kind, width, entries):
    if kind not in NAMES or not 1 <= width <= 64 or not 1 <= entries <= 1024:
        raise ValueError('invalid generated power check parameters')
    head = f'module rvw_{kind}(input clk, reset, '
    if kind == 'clock_gate':
        ports = 'input enable, source_low, clock_edge, work_pending, wakeup'
        body = f'''reg previous_enable=0, armed=0;
reg [{max(1, entries.bit_length())-1}:0] wake_age=0;
reg waiting=0;
always @(posedge clk) begin
 if(reset) begin previous_enable<=enable; armed<=0; waiting<=0; wake_age<=0; end
 else begin
  armed<=1;
  if(armed && enable != previous_enable) assert(source_low);
  assert(enable || !clock_edge);
  assert(enable || !work_pending);
  previous_enable<=enable;
  if(wakeup && !waiting) begin waiting<=1; wake_age<=0; end
  if(waiting) begin
   assert(wake_age < {entries});
   wake_age <= wake_age + 1;
  end
  if(enable && clock_edge) begin waiting<=0; wake_age<=0; end
 end
end'''
    elif kind == 'isolation':
        ports = f'input power_good, isolated, consumer_use, output_valid, input [{width-1}:0] value, clamp'
        body = '''reg previous_isolated=0, previous_power=1, armed=0;
always @(posedge clk) begin
 if(reset) begin armed<=0; previous_isolated<=isolated; previous_power<=power_good; end
 else begin
  armed<=1;
  if(isolated) assert(value == clamp);
  if(!power_good) begin assert(isolated); assert(!output_valid); end
  if(consumer_use) assert(output_valid || isolated);
  if(armed && previous_power && !power_good) assert(previous_isolated);
  previous_isolated<=isolated; previous_power<=power_good;
 end
end'''
    elif kind == 'retention':
        ports = f'input power_good, save, restore, functional_use, input [{width-1}:0] state'
        body = f'''reg [{width-1}:0] saved;
reg have_save=0, need_restore=0, check_restore=0;
always @(posedge clk) begin
 if(reset) begin have_save<=0; need_restore<=0; check_restore<=0; end
 else begin
  if(check_restore) assert(state == saved);
  check_restore<=0;
  if(save) begin assert(power_good); assert(!restore); saved<=state; have_save<=1; end
  if(!power_good) begin assert(have_save); need_restore<=1; assert(!functional_use); end
  if(restore) begin
   assert(power_good); assert(have_save); assert(need_restore);
   check_restore<=1; need_restore<=0;
  end
  if(functional_use) begin assert(power_good); assert(!need_restore); end
 end
end'''
    else:
        ports = f'''input functional_mode, scan_enable, test_enable, authorized,
input power_good, protected_write, test_access, input [{width-1}:0] test_output, clamp'''
        body = '''always @(posedge clk) if(!reset) begin
 if(functional_mode) begin assert(!scan_enable); assert(!test_enable); assert(test_output == clamp); end
 if(test_access || protected_write || scan_enable || test_enable) begin
  assert(authorized); assert(power_good); assert(!functional_mode);
 end
end'''
    return head + ports + ');\n' + body + '\nendmodule\n'
