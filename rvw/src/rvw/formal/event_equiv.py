"""Explicit sample-to-sample input setup constraints for clock-event comparisons."""

def constraints(args, ports):
    entries=args.stable_at_edge
    allowed={p.name:p for p in ports if p.direction=='input' and p.name not in (args.clock,args.reset)}
    if len(entries)!=len(set(entries)) or set(entries)-set(allowed):
        raise ValueError('stable-at-edge needs distinct data input ports')
    if not entries:return []
    lines=['reg rvw_previous_clock=0;',f'always @($global_clock) rvw_previous_clock <= {args.clock};']
    for index,name in enumerate(entries):
        width=allowed[name].width
        lines += [f'reg [{width-1}:0] rvw_previous_input{index};',
                  'always @($global_clock) begin',
                  f'if ({args.clock} && !rvw_previous_clock) assume ({name} == rvw_previous_input{index});',
                  f'rvw_previous_input{index} <= {name}; end']
    return lines
