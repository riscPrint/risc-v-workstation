#!/usr/bin/env bash
# Build the SpinalWaves Rust tools and put them on PATH.
#
#   scripts/install.sh [--prefix DIR] [--only check|surfer] [--test] [--copy]
#
#   --prefix DIR   where to install (default: $SPINALWAVES_BIN or ~/.local/bin)
#   --only X       build/install only spinalwaves-check (check) or surfer-tywaves (surfer)
#   --test         also run `cargo test` for third_party/tywaves-rs and the checker
#   --copy         copy the binaries instead of symlinking them (symlinks follow rebuilds)
#
# Installs:  spinalwaves-check  (tools/spinalwaves-check)
#            surfer-tywaves     (surfer-tywaves/, uses third_party/tywaves-rs)
# The first surfer-tywaves release build takes several minutes (LTO).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${SPINALWAVES_BIN:-$HOME/.local/bin}"
ONLY=""
TEST=0
COPY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) PREFIX="$2"; shift 2 ;;
    --only) ONLY="$2"; shift 2 ;;
    --test) TEST=1; shift ;;
    --copy) COPY=1; shift ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "install.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done
case "$ONLY" in ""|check|surfer) ;; *) echo "install.sh: --only must be check or surfer" >&2; exit 2 ;; esac

command -v cargo >/dev/null || { echo "install.sh: cargo not found on PATH" >&2; exit 1; }

# Verify the local patches and Cargo.lock files before Cargo can run.
python3 "$ROOT/scripts/package-source.py"
NOTICES="$PREFIX/../share/spinalwaves"
mkdir -p "$NOTICES"
cp "$ROOT/surfer-tywaves/LICENSE-EUPL-1.2.txt" "$NOTICES/"
cp "$ROOT/vendor-lock.json" "$NOTICES/"
python3 "$ROOT/scripts/package-source.py" --out "$NOTICES/source.tar.gz"

install_bin() {  # install_bin <built binary> <name>
  local src="$1" name="$2"
  [ -x "$src" ] || { echo "install.sh: missing build output $src" >&2; exit 1; }
  mkdir -p "$PREFIX"
  rm -f "$PREFIX/$name"
  if [ "$COPY" = 1 ]; then cp "$src" "$PREFIX/$name"; else ln -s "$src" "$PREFIX/$name"; fi
  echo "installed $PREFIX/$name -> $src"
}

if [ "$TEST" = 1 ]; then
  echo "== cargo test: third_party/tywaves-rs"
  cargo test --locked --manifest-path "$ROOT/third_party/tywaves-rs/Cargo.toml"
  echo "== cargo test: tools/spinalwaves-check"
  cargo test --locked --manifest-path "$ROOT/tools/spinalwaves-check/Cargo.toml"
fi

if [ "$ONLY" != surfer ]; then
  echo "== cargo build --release: tools/spinalwaves-check"
  cargo build --release --locked --manifest-path "$ROOT/tools/spinalwaves-check/Cargo.toml"
  install_bin "$ROOT/tools/spinalwaves-check/target/release/spinalwaves-check" spinalwaves-check
fi

if [ "$ONLY" != check ]; then
  echo "== cargo build --release: surfer-tywaves"
  cargo build --release --locked --manifest-path "$ROOT/surfer-tywaves/Cargo.toml" -p surfer-tywaves
  VIEWER="${CARGO_TARGET_DIR:-$ROOT/surfer-tywaves/target}/release/surfer-tywaves"
  install_bin "$VIEWER" surfer-tywaves
  if [ "$(uname -s)" = Darwin ]; then
    python3 "$ROOT/scripts/package-app.py" "$VIEWER" "$NOTICES" \
      "$PREFIX/SpinalWaves.app"
    echo "installed $PREFIX/SpinalWaves.app"
  fi
fi

case ":$PATH:" in
  *":$PREFIX:"*) ;;
  *) echo "note: $PREFIX is not on PATH; add:  export PATH=\"$PREFIX:\$PATH\"" ;;
esac
