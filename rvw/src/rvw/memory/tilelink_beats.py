"""Collect accepted TL-C data beats before applying whole-message checks."""


def wrap(inner, fields, source_bits, sink_bits, address_bits, data_bits, size_bits, line_bytes, bound):
    line_bits = line_bytes*8
    beats = line_bits//data_bits
    if beats <= 1:
        return inner
    widths = dict(source=source_bits, sink=sink_bits, address=address_bits, data=data_bits, size=size_bits)
    ports = ['input wire clock', 'input wire reset', f'input wire [{line_bits-1}:0] expected_data']
    for client in range(2):
        for name, width in fields.items():
            width = widths.get(width, width)
            ports.append(f'input wire [{width-1}:0] c{client}_{name}')
    code = inner.replace('module rvw_tlc_monitor(', 'module rvw_tlc_message_monitor(', 1)
    code += '\nmodule rvw_tlc_monitor(\n  '+',\n  '.join(ports)+'\n);\n'
    connections = ['.clock(clock)', '.reset(reset)', '.expected_data(expected_data)']
    for client in range(2):
        for channel in ('c', 'd'):
            prefix = f'c{client}_{channel}'
            header_fields = [name for name in fields if name.startswith(channel+'_') and name not in
                             (channel+'_valid', channel+'_ready', channel+'_data')]
            header_bits = sum(widths.get(fields[name], fields[name]) for name in header_fields)
            header = '{' + ','.join(f'c{client}_{name}' for name in header_fields) + '}'
            data = f'{prefix}_data'
            opcode = f'{prefix}_opcode'
            has_data = f'{opcode}[0]' if channel == 'c' else f'({opcode}==5)'
            error = f'{prefix}_corrupt' if channel == 'c' else f'({prefix}_corrupt || {prefix}_denied)'
            code += f'''integer {prefix}_count;
integer {prefix}_age;
reg [{line_bits-1}:0] {prefix}_buffer;
reg [{line_bits-1}:0] {prefix}_full;
reg [{header_bits-1}:0] {prefix}_header;
wire {prefix}_last = !({has_data}) || {prefix}_count=={beats-1};
always @* begin
  {prefix}_full={prefix}_buffer;
  {prefix}_full[{prefix}_count*{data_bits} +: {data_bits}]={data};
end
always @(posedge clock) begin
  if(reset) begin
    {prefix}_count<=0; {prefix}_age<=0; {prefix}_buffer<=0; {prefix}_header<=0;
  end else begin
    if({prefix}_count!=0) begin
      {prefix}_age<={prefix}_age+1;
      if({prefix}_age>={bound}) $fatal(1,"rvw TL-C incomplete data message");
    end
    if({prefix}_valid && {prefix}_ready) begin
      if({error}) $fatal(1,"rvw TL-C data error outside success profile");
      if({prefix}_count==0) {prefix}_header<={header};
      else if({prefix}_header!={header}) $fatal(1,"rvw TL-C data message header changed");
      {prefix}_buffer<={prefix}_full;
      if({prefix}_last) begin {prefix}_count<=0; {prefix}_age<=0; end
      else begin
        {prefix}_count<={prefix}_count+1;
        if({prefix}_count==0) {prefix}_age<=0;
      end
    end
  end
end
'''
        for name in fields:
            port = f'c{client}_{name}'
            if name in ('c_data', 'd_data'):
                value = port.removesuffix('_data')+'_full'
            elif name in ('c_valid', 'd_valid'):
                value = port+' && '+port.removesuffix('_valid')+'_last'
            else:
                value = port
            connections.append(f'.{port}({value})')
    code += '\nrvw_tlc_message_monitor complete_messages(\n  '+',\n  '.join(connections)+'\n);\nendmodule\n'
    return code
