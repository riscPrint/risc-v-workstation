"""Direct DMI and the public TAP CLI use the composed core's real debug pins."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import cocotb
from cocotb.triggers import FallingEdge,RisingEdge,ClockCycles
from rvw.sim.bench import start


@cocotb.test()
async def debug(d):
    d.gpio_input.value=0
    if d._name=='DmiSoc':
        for field in ('valid','payload_write','payload_address','payload_data'):
            getattr(d,'debug_dmi_cmd_'+field).value=0
    else:
        d.debug_jtag_tck.value=0;d.debug_jtag_tms.value=1;d.debug_jtag_tdi.value=0
    await start(d);await ClockCycles(d.clk,150)
    assert int(d.gpio_output.value)==0x12345678,'CPU_DID_NOT_REACH_COMPOSED_GPIO'
    assert int(d.core_retired.value)>0,'CPU_DID_NOT_RETIRE'
    if d._name=='DmiSoc':await dmi(d)
    else:await tap_cli(d)


async def dmi(d):
    accesses=0
    async def transfer(address,data=None):
        nonlocal accesses
        await FallingEdge(d.clk)
        d.debug_dmi_cmd_valid.value=1;d.debug_dmi_cmd_payload_write.value=int(data is not None)
        d.debug_dmi_cmd_payload_address.value=address;d.debug_dmi_cmd_payload_data.value=data or 0
        response=None;accepted=False
        for _ in range(200):
            await RisingEdge(d.clk)
            if int(d.debug_dmi_rsp_valid.value):
                assert not int(d.debug_dmi_rsp_payload_error.value),'DMI_RESPONSE_ERROR'
                response=int(d.debug_dmi_rsp_payload_data.value)
            if not accepted and int(d.debug_dmi_cmd_ready.value):accepted=True
            await FallingEdge(d.clk)
            if accepted:d.debug_dmi_cmd_valid.value=0
            if accepted and response is not None:break
        else:raise AssertionError('DMI_TIMEOUT')
        accesses+=1
        return response
    status=await transfer(0x11);assert status&15==2,'DMI_DMSTATUS_VERSION'
    await transfer(0x10,1)
    await ClockCycles(d.clk,10)
    await transfer(0x10,0x80000001)
    for _ in range(30):
        status=await transfer(0x11)
        if status & (1<<9):break
    assert status&(1<<9),'DMI_HALT'
    before=int(d.core_retired.value);await ClockCycles(d.clk,30)
    assert int(d.core_retired.value)==before,'HALTED_CPU_RETIRED'
    await transfer(0x10,0x40000001)
    for _ in range(30):
        status=await transfer(0x11)
        if status & (1<<11):break
    assert status&(1<<11),'DMI_RESUME'
    await ClockCycles(d.clk,30)
    assert int(d.core_retired.value)>before,'RESUMED_CPU_DID_NOT_RETIRE'
    Path('debug-checks.json').write_text(json.dumps(dict(profile='rv32im_dmi',accesses=accesses,halted_retired=before,
        resumed_retired=int(d.core_retired.value),gpio=int(d.gpio_output.value),ndmreset_bound=False),indent=2)+'\n')


async def tap_cli(d):
    server=socket.socket();server.bind(('127.0.0.1',0));server.listen(1);server.setblocking(False)
    port=server.getsockname()[1]
    log=Path('tap-cli.log').open('w');process=None;client=None;commands=0
    deadline=time.monotonic()+45
    try:
        process=subprocess.Popen([sys.executable,'-m','rvw','debug','tap','--port',str(port),'--out','tap-results'],stdout=log,stderr=log)
        while client is None:
            assert time.monotonic()<deadline,'TAP_CLIENT_CONNECT_TIMEOUT'
            try:client,_=server.accept()
            except BlockingIOError:time.sleep(0.001);await ClockCycles(d.clk,1)
        client.setblocking(False)
        while process.poll() is None:
            assert time.monotonic()<deadline,'TAP_CLI_TIMEOUT'
            try:chunk=client.recv(65536)
            except BlockingIOError:time.sleep(0.001);await ClockCycles(d.clk,1);continue
            if not chunk:time.sleep(0.001);await ClockCycles(d.clk,1);continue
            reply=bytearray()
            for byte in chunk:
                if 48<=byte<=55:
                    value=byte-48
                    d.debug_jtag_tck.value=value>>2&1;d.debug_jtag_tms.value=value>>1&1;d.debug_jtag_tdi.value=value&1
                    await ClockCycles(d.clk,1);commands+=1
                elif byte==82:reply.append(49 if int(d.debug_jtag_tdo.value) else 48)
                elif byte in (66,98,81):pass
                else:raise AssertionError('UNSUPPORTED_REMOTE_BITBANG_BYTE')
            if reply:client.sendall(reply)
        log.flush()
        result=json.loads(Path('tap-results/results.json').read_text())
        counts={status:sum(t['status']==status for t in result['tests']) for status in ('pass','fail','inconclusive')}
        Path('debug-checks.json').write_text(json.dumps(dict(profile='rv32im_jtag',commands=commands,tap=counts,
            retired=int(d.core_retired.value),gpio=int(d.gpio_output.value),ndmreset_bound=False),indent=2)+'\n')
        assert process.returncode==0,'PUBLIC_TAP_CLI_FAILED'
        assert len(result['tests'])==9 and counts['pass']==9,'ALL_NINE_TAP_CHECKS_REQUIRED'
    finally:
        if process is not None and process.poll() is None:process.kill();process.wait(timeout=5)
        if client is not None:client.close()
        server.close();log.close()
