#!/usr/bin/env python3
"""Execute the generated monitor on recorded physical projection samples."""
import argparse,json,shutil,sqlite3
from pathlib import Path
from rvw.common.proc import run_group
from rvw.memory.tilelink_bind import FIELDS

def replay(database,binding,capture,out):
    binding=Path(binding);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    profile=json.loads((binding/'profile.json').read_text())
    connection=sqlite3.connect(database);connection.row_factory=sqlite3.Row
    signals={r['id']:dict(r) for r in connection.execute('SELECT * FROM signals')};connection.close()
    ports={name:signals[profile[name]] for name in ('clock','reset','expected_data')}
    for hart,client in enumerate(profile['clients']):
        for field in FIELDS:ports[f'c{hart}_{field}']=signals[client['signals'][field]]
    rows=[json.loads(line) for line in Path(capture).read_text().splitlines()]
    if not rows:raise ValueError('no RTL samples')
    if not any(int(row['reset'],0) for row in rows):raise ValueError('sampled reset events are required')
    simulator=shutil.which('iverilog');runtime=shutil.which('vvp')
    if not simulator or not runtime:raise ValueError('Icarus and vvp required')
    def run(corrupt):
        name='fault' if corrupt else 'control'
        text=['module tb;']
        for port,signal in ports.items():text.append(f'reg [{signal["width"]-1}:0] {port}=0;')
        text += ['rvw_tlc_monitor monitor('+','.join(f'.{p}({p})' for p in ports)+');','initial begin']
        planted=False
        for row in rows:
            text.append('clock=0;')
            for port,signal in ports.items():
                if port=='clock':continue
                value=int(row[signal['name']],0)
                if corrupt and not planted and port=='c0_d_data' and int(row[ports['c0_d_valid']['name']],0) and int(row[ports['c0_d_ready']['name']],0) and int(row[ports['c0_d_opcode']['name']],0)==5:
                    value^=1;planted=True
                text.append(f"{port}={signal['width']}'h{value:x};")
            text.append('#5;')
            if int(row[ports['clock']['name']],0):text.append('clock=1;')
            text.append('#5;')
        text.append('clock=0;')
        text.extend(f'{port}=0;' for port in ports if port.endswith('_valid'))
        text.append(f'repeat({profile["bound_cycles"]+2}) begin #5; clock=1; #5; clock=0; end')
        text+=['$finish; end endmodule']
        if corrupt and not planted:raise ValueError('no selected GrantData beat for fault control')
        source=out/f'{name}.sv';source.write_text('\n'.join(text)+'\n');binary=out/name
        compile=run_group([simulator,'-g2012','-s','tb','-o',str(binary),str(binding/'monitor/rvw_tlc_monitor.sv'),str(source)],capture=True,timeout=60)
        if compile.returncode or compile.timed_out:raise ValueError(compile.stderr)
        result=run_group([runtime,str(binary)],capture=True,timeout=60)
        (out/f'{name}.log').write_text(result.stdout+result.stderr)
        return dict(returncode=result.returncode,timed_out=result.timed_out,monitor_violation='rvw TL-C monitor violation' in result.stdout+result.stderr)
    control=run(False);fault=run(True)
    if control['timed_out'] or fault['timed_out'] or control['returncode'] or not fault['returncode'] or not fault['monitor_violation']:raise ValueError(dict(control=control,fault=fault))
    report=dict(schema='rvw.cached-monitor-replay/1',status='pass',samples=len(rows),reset_samples=sum(bool(int(row['reset'],0)) for row in rows),control=control,fault=fault,
                scope='generated monitor replay of sampled RTL line projection; bind file generated, in-simulation bind NOT RUN')
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('database','binding','capture','out'):p.add_argument('--'+name,required=True)
    a=p.parse_args();print(json.dumps(replay(a.database,a.binding,a.capture,a.out),indent=2))
