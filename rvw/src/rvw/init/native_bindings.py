"""Native consumers of the reviewed mapped adapter declaration."""
import json


def files(core):
    """Export the simulation elaboration once for native consumers."""
    export = '''import java.io.File
import java.nio.file.{Files, Paths}
import riscvsim._
object RvwExport {
  def main(args: Array[String]): Unit = {
    val map = CoreMap.load(new File("core-map.json"))
    val adapter = new MappedAdapter(map)
    val sources = adapter.elaborate(ModelKey(map.config), new File("out/export"))
    val bytes = sources.map(f => new String(Files.readAllBytes(f.toPath), "UTF-8")).mkString("\\n")
    Files.write(Paths.get("out/export/core.v"), bytes.getBytes("UTF-8"))
  }
}
'''
    script = '''#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cd "$here"
: "${RVW_HOME:?Set RVW_HOME}"
exec "$RVW_HOME/scripts/with-lock.sh" "${RVW_SBT_LOCK:-sbt-CORE}" nice -n 10 sbt "runMain RvwExport"
'''.replace('sbt-CORE', 'sbt-' + core['core'])
    from rvw.checks.declarations import scaffold
    return {'rvw/src/main/scala/RvwExport.scala': export, 'rvw/export-rtl.sh': script,
            'rvw/templates/checks.micro.json': json.dumps(scaffold(),indent=2)+'\n',
            'rvw/templates/DeclaredCoreChecks.scala': '''// Review-only stub. Add a call in the sampling domain and enable SpinalChecks.
// Supply real conditions. Do not tie the trigger or failure to constants.
import spinal.core._
import spinalchecks.DeclaredChecks
object DeclaredCoreChecks {
  def bind(kind: String, name: String, meaning: String, active: Bool, failed: Bool): Unit =
    DeclaredChecks.rule(kind, name, meaning, trigger = active)(failed)
}
''' }


def security(core):
    if core['xlen'] != 32 or not core['rvfi']:
        return {}
    buses = []
    roles = dict(cmd_valid='cmd_valid', cmd_ready='cmd_ready', address='cmd_address',
                 write='cmd_write', wdata='cmd_data', mask='cmd_mask',
                 rsp_valid='rsp_valid', rdata='rsp_data', error='rsp_error')
    for bus in core['buses']:
        if bus['protocol'] != 'req-rsp':
            return {}
        buses.append(dict(name=bus['name'], kind='data' if 'write' in bus['signals'] else 'fetch',
                          latency=1, write_response=bus['write_response'],
                          **{roles[k]: v for k, v in bus['signals'].items() if k in roles}))
    top = core['top']
    binding = dict(schema='rvw.sec-core/1', name=core['core'], isa=core['isa'], march=core['isa'],
                   rtl=['../out/export/core.v'], top=top.get('module', top.get('class', '').split('.')[-1]),
                   clock=top.get('clock', 'clk'), reset=top.get('reset', 'reset'), reset_cycles=4,
                   ram=core['ram'], max_cycles=20000, platform='../cosim.json',
                   link='../programs/link.ld', buses=buses, retire=dict(kind='rvfi', **core['rvfi']),
                   ties=core['constants'], csr_signals={})
    # The native harness currently implements active-high reset only.
    if top.get('reset_active', 'high') != 'high':
        return {}
    case = '''.section .text.init
.globl _start
_start:
# RVW_SETUP
# RVW_PROGRAM
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
# RVW_DATA
'''
    pair = dict(contract='constant-time', clauses=['pc', 'memory'],
                observations=['cycles', 'retire_cycles', 'bus_timing'], public={'reset': 'cold'},
                program=['div x10, x6, x7' if 'm' in core['isa'] else 'add x10, x6, x7'], secrets=[{'x6': 7, 'x7': 3}, {'x6': 21, 'x7': 4}],
                minimize_runs=0, timeout=90,
                adapter_command=['{python}', '-m', 'rvw.sec.core_adapter', '--binding', 'core.json',
                                 '--template', 'case.S', '{request}', '{out}'])
    bus = next((b for b in core['buses'] if 'write' in b['signals']), core['buses'][0])
    policy = dict(memory_regions=[dict(symbol='scratch', size='0x4')],
                  sinks=[dict(signal=bus['signals']['address'])])
    flow = case.replace('# RVW_SETUP', '').replace('# RVW_PROGRAM', '  la t0, scratch\n  lw t1, 0(t0)\n  addi t1, t1, 1').replace('# RVW_DATA', '.balign 4\n.globl scratch\nscratch: .word 7')
    return {'rvw/sec/flow.S': flow, 'rvw/sec/core.json': json.dumps(binding, indent=2)+'\n',
            'rvw/sec/constant-time.json': json.dumps(pair, indent=2)+'\n',
            'rvw/sec/case.S': case, 'rvw/sec/flow.json': json.dumps(policy, indent=2)+'\n'}

