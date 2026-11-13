#!/usr/bin/env bash
# Build outside the repository. Supply the pinned Linux checkout and LLVM tools.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="${1:?Linux source checkout}"
out="${2:?External output directory}"
RVW_LINUX_REVISION=9b5aad3a7498c261116a0251fe57f14ba9c4c6cf
[[ "$(git -C "$source_dir" rev-parse HEAD)" == "$RVW_LINUX_REVISION" ]] || { echo 'Linux revision mismatch' >&2; exit 2; }
mkdir -p "$out"
out="$(cd "$out" && pwd)"
: "${RVW_LLVM_BIN:?Set the LLVM bin directory}"
: "${RVW_LLD_BIN:?Set the LLD bin directory}"
export PATH="${RVW_GNU_SED_BIN:+$RVW_GNU_SED_BIN:}$RVW_LLVM_BIN:$RVW_LLD_BIN:$PATH"
"${RISCV_GCC:-riscv64-unknown-elf-gcc}" -march=rv64imac -mabi=lp64 -nostdlib -static \
  -Wl,--build-id=none -Wl,-e,_start "$here/init.S" -o "$out/init-elf"
"${RVW_PYTHON:-python3}" "$here/initramfs.py" "$out/init-elf" "$out/initramfs.cpio"
make_args=(-C "$source_dir" O="$out" ARCH=riscv LLVM=1 HOSTCC=clang HOSTCXX=clang++ \
  HOSTCFLAGS=-Wno-error=unused-command-line-argument)
if [[ -n "${RVW_HOST_ELF_HEADER:-}" ]]; then
  mkdir -p "$out/host-include"
  cp "$RVW_HOST_ELF_HEADER" "$out/host-include/elf.h"
  host_flags="-Wno-error=unused-command-line-argument -I$out/host-include"
  if [[ "$(uname -s)" == Darwin ]]; then
    printf '#include <unistd.h>\n#define uuid_t rvw_linux_uuid_t\n' > "$out/host-include/macos-host.h"
    make_args+=("HOSTCFLAGS_file2alias.o=-include $out/host-include/macos-host.h")
  fi
  make_args+=("HOSTCFLAGS=$host_flags")
fi
nice -n 10 gmake "${make_args[@]}" allnoconfig
"$source_dir/scripts/config" --file "$out/.config" \
  -e EXPERT -e SLUB -e SLUB_TINY -e CC_OPTIMIZE_FOR_SIZE -e 64BIT -e MMU -e RISCV_SBI -e RISCV_ISA_C -e BINFMT_ELF -e PRINTK \
  -e BLK_DEV_INITRD -e TTY -e SERIAL_8250 -e SERIAL_8250_CONSOLE \
  -e SERIAL_OF_PLATFORM -e OF -e RISCV_TIMER -e HIGH_RES_TIMERS \
  -e INITRAMFS_COMPRESSION_NONE -d INITRAMFS_COMPRESSION_GZIP \
  -d RD_GZIP -d RD_BZIP2 -d RD_LZMA -d RD_XZ -d RD_LZO -d RD_LZ4 -d RD_ZSTD \
  -d PROC_FS -d SYSFS -d SYSCTL -d IO_URING -d EPOLL -d SIGNALFD -d TIMERFD -d EVENTFD -d AIO \
  -d SMP -d FPU -d VECTOR -d MODULES -d BLOCK -d NET -d STACKPROTECTOR \
  -d RANDOMIZE_BASE -d SECURITY -d DEBUG_KERNEL \
  --set-str INITRAMFS_SOURCE "$out/initramfs.cpio" \
  --set-str CMDLINE 'console=ttyS0,115200 earlycon=uart8250,mmio,0x10000000 keep_bootcon rdinit=/init lpj=1000 loglevel=7'
nice -n 10 gmake "${make_args[@]}" olddefconfig
nice -n 10 gmake "${make_args[@]}" -j2 Image
