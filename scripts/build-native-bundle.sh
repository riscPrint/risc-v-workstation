#!/usr/bin/env bash
# CI entry point. One tool per native job; no containers.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
tool="${1:?tool required}"
# Read the installer's immutable source identities without executing it.
pin() { sed -n "s/^${1}_revision=//p" scripts/install.sh; }
source_tree() {
  local name="$1" url="$2" revision="$3"
  src="$root/.tools/src/$name"
  if [ ! -d "$src/.git" ]; then
    mkdir -p "$src"
    git -C "$src" init
    git -C "$src" remote add origin "$url"
    git -C "$src" fetch --depth 1 origin "$revision"
    git -C "$src" checkout --detach FETCH_HEAD
  fi
  [ "$(git -C "$src" rev-parse HEAD)" = "$revision" ]
  git -C "$src" diff --exit-code HEAD
}
mkdir -p .tools
prefix="$root/.tools/$tool"
case "$tool" in
  verilator)
    source_tree verilator https://github.com/verilator/verilator.git "$(pin verilator)"
    (cd "$src"; autoconf; ./configure --prefix="$prefix"; make -j2; make install)
    "$prefix/bin/verilator" --version
    ;;
  gcc)
    source_tree gcc https://github.com/riscv-collab/riscv-gnu-toolchain.git "$(pin gcc)"
    git -C "$src" submodule update --init --recursive --depth 1
    (cd "$src"; ./configure --prefix="$prefix" --with-arch=rv64gc --with-abi=lp64d --disable-multilib; make -j2)
    "$prefix/bin/riscv64-unknown-elf-gcc" --version
    ;;
  spike)
    source_tree spike https://github.com/riscv-software-src/riscv-isa-sim.git "$(pin spike)"
    mkdir -p "$src/build"
    (cd "$src/build"; ../configure --prefix="$prefix"; make -j2; make install)
    # Static linkage permits relocation without changing the bound shim bytes.
    # Spike always builds a shared library. Combine its static dependencies for the shim.
    rm -f "$prefix/lib/libriscv.so" "$prefix/lib/libriscv.dylib"
    if [ "$(uname -s)" = Darwin ]; then
      libtool -static -o "$prefix/lib/libriscv.a" "$src/build/libriscv.a" "$src/build/libsoftfloat.a" "$src/build/libfdt.a"
    else
      (cd "$src/build"; printf 'CREATE %s\nADDLIB libriscv.a\nADDLIB libsoftfloat.a\nADDLIB libfdt.a\nSAVE\nEND\n' "$prefix/lib/libriscv.a" | ar -M)
    fi
    mkdir -p "$prefix/share/rvw"
    printf '{"version":"1.1.1-dev","revision":"%s","origin":"rvw-source-build"}\n' "$(pin spike)" > "$prefix/share/rvw/spike-source.json"
    SPIKE_PREFIX="$prefix" Cosim/build.sh "$prefix/rvw-shim/librvw_spike.so"
    ;;
  sail)
    # Repackage the verified upstream native build. Do not label this a source build.
    scripts/install-sail.sh
    mkdir -p "$prefix"
    cp -R .tools/sail-0.15/. "$prefix/"
    "$prefix/bin/sail_riscv_sim" --version
    ;;
  gem5)
    scripts/install.sh --yes --with-gem5
    src="$root/.tools/src/gem5-v25.1.0.1"
    mkdir -p "$prefix/bin"
    cp .tools/src/gem5-v25.1.0.1/build/RISCV/gem5.opt "$prefix/bin/"
    ;;
  *) echo 'Unknown native tool' >&2; exit 2 ;;
esac
# Keep the native dependency report with each tool. System dependencies are prerequisites.
mkdir -p "$prefix/share/rvw/licenses"
if [ -n "${src:-}" ]; then
  find "$src" -maxdepth 1 -type f \( -name 'COPYING*' -o -name 'LICENSE*' \) -exec cp {} "$prefix/share/rvw/licenses/" \;
  git -C "$src" remote get-url origin > "$prefix/share/rvw/source.txt"
  git -C "$src" rev-parse HEAD >> "$prefix/share/rvw/source.txt"
fi
if [ "$(uname -s)" = Darwin ]; then
  find "$prefix/bin" -type f -perm -111 -exec otool -L {} \; > "$prefix/share/rvw/dependencies.txt" 2>&1 || true
else
  find "$prefix/bin" -type f -executable -exec ldd {} \; > "$prefix/share/rvw/dependencies.txt" 2>&1 || true
fi
cp scripts/README.md "$prefix/share/rvw/BUNDLE-README.md"
python3 scripts/native-bundle.py pack --home "$root" --tool "$tool" --source "$prefix" --output dist/native
