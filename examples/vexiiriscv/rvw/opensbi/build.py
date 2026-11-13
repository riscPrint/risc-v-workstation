"""Build pinned OpenSBI with only the example's UART and CLINT drivers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
from rvw.common.proc import run_group

REVISION='bd613dd92113f683052acfb23d9dc8ba60029e0a'


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--source',type=Path,required=True,help='private OpenSBI checkout')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--llvm-prefix',type=Path,required=True)
    a=p.parse_args()
    source=a.source.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    revision=run_group(['git','-C',str(source),'rev-parse','HEAD'],capture=True,timeout=10)
    if revision.returncode or revision.stdout.strip()!=REVISION:raise ValueError('OpenSBI revision differs')
    here=Path(__file__).resolve().parent
    config=(here/'rvw/configs/defconfig').read_bytes()
    digest=hashlib.sha256(config).hexdigest()
    llvm=a.llvm_prefix.resolve()
    env=dict(os.environ,PATH=str(llvm)+os.pathsep+os.environ['PATH'])
    ld=shutil.which('ld.lld',path=env['PATH'])
    if not ld:raise ValueError('LLVM lld required')
    command=['nice','-n','10','gmake','-C',str(source),'-j2','O='+str(out),
        'build_dir='+str(out),'platform_dir_path='+str(here),'platform_parent_dir='+str(here),
        'PLATFORM=rvw','PLATFORM_DIR='+str(here),'LLVM=1',
        'CC='+str(llvm/'clang'),'AR='+str(llvm/'llvm-ar'),
        'OBJCOPY='+str(llvm/'llvm-objcopy'),'LD='+ld,
        'CROSS_COMPILE=riscv64-unknown-elf-',
        'PLATFORM_RISCV_ISA=rv64ima_zicsr_zifencei','PLATFORM_RISCV_ABI=lp64',
        'FW_JUMP=y','FW_PAYLOAD=n','FW_DYNAMIC=n','FW_OPTIONS=1',
        'FW_TEXT_START=0x80200000','FW_JUMP_ADDR=0x80400000','FW_JUMP_FDT_OFFSET=',
        'platform-cflags-y=-Wno-error=unused-but-set-variable -Wno-error=unused-but-set-global']
    built=run_group(command,capture=True,timeout=600,env=env)
    (out/'build.log').write_text(built.stdout+built.stderr)
    if built.returncode:raise RuntimeError(built.stdout[-2000:]+built.stderr[-2000:])
    firmware=out/'platform/rvw/firmware/fw_jump.bin'
    compiler=run_group([str(llvm/'clang'),'--version'],capture=True,timeout=10)
    result=dict(compiler=compiler.stdout.splitlines()[0],schema='rvw.vexii-opensbi-build/1',revision=REVISION,config_sha256=digest,platform_sha256=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((here/'rvw').rglob('*')) if p.is_file())).hexdigest(),
        firmware_sha256=hashlib.sha256(firmware.read_bytes()).hexdigest())
    (out/'build.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
