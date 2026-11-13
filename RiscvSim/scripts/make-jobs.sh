#!/usr/bin/env bash
# Stand-in for `make` (via SPINAL_MAKE_CMD) that replaces Spinal's `-j<all cores>` with
# -j$RISCVSIM_MAKE_JOBS (default 4), so Verilator C++ builds share the machine.
set -e
# Spinal's legacy coverage writer collapses hierarchy unless the context opts in.
# Patch only its generated wrapper. This script's bytes enter native identity.
build_dir="$PWD"
expect_dir=0
for a in "$@"; do
  if [ "$expect_dir" = 1 ]; then build_dir="$a"; expect_dir=0; continue; fi
  case "$a" in -C) expect_dir=1 ;; -C?*) build_dir="${a#-C}" ;; esac
done
for wrapper in "$build_dir"/*__spinalWrapper.cpp; do
  [ -f "$wrapper" ] || continue
  metadata="${wrapper%__spinalWrapper.cpp}__verFiles.dat"
  [ -f "$metadata" ] || continue
  # The older compiler has shared counters. Forcing its writer would invent
  # instance observations from shared counts, so keep its normal collapse rule.
  perl -ne 'if (/^C /) {
      while (/(?:^|\s|\")--(no-)?coverage-per-instance(?=\s|\")/g) {$enabled = $1 ? 0 : 1}
    } END {exit !$enabled}' "$metadata" || continue
  perl -0777 -i -pe 'if (!/forcePerInstance\(true\)/) {
    s/VerilatedCov::write\(/Verilated::threadContextp()->coveragep()->forcePerInstance(true);\n      VerilatedCov::write(/g;
  }' "$wrapper"
done
# Older SpinalHDL wrappers (for example NaxRiscv's pinned revision) access public signals by
# their raw names. Verilator 5 encodes a "_" that follows "_" in C++ member names ("a__b" becomes
# "a___05Fb"). Use the encoded name only where the generated headers lack the raw one and have
# the encoded one; newer wrappers already match the headers and stay unchanged.
for wrapper in "$build_dir"/*__spinalWrapper.cpp; do
  [ -f "$wrapper" ] || continue
  perl -e '
    use File::Glob qw(bsd_glob);
    my ($wrapper, $dir) = @ARGV; my %ids;
    for my $h (bsd_glob("$dir/*.h")) {
      open(my $f, "<", $h) or next; local $/; my $t = <$f>; close $f;
      $ids{$_} = 1 for ($t =~ /\b([A-Za-z_][A-Za-z0-9_]*)\b/g);
    }
    open(my $f, "<", $wrapper) or exit 0; local $/; my $t = <$f>; close $f;
    my $n = ($t =~ s{(\btop(?:->[A-Za-z_][A-Za-z0-9_]*)*->)([A-Za-z_][A-Za-z0-9_]*__[A-Za-z0-9_]*)}{
      my ($p, $m) = ($1, $2); (my $e = $m) =~ s/(?<=_)_/__05F/g;
      (!$ids{$m} && $ids{$e}) ? "$p$e" : "$p$m" }ge);
    if ($n) { open($f, ">", $wrapper) or die; print $f $t; close $f; }
  ' "$wrapper" "$build_dir"
done
args=()
for a in "$@"; do
  case "$a" in -j*) ;; *) args+=("$a") ;; esac
done
# Command-line make variables override the tool names in verilated.mk.
# An unpinned direct JVM launch cannot earn a conclusive result or native reuse.
if [ -n "${RISCVSIM_PINNED_BIN:-}" ]; then
  args+=("CXX=$RISCVSIM_PINNED_CXX" "LINK=$RISCVSIM_PINNED_LINK" "AR=$RISCVSIM_PINNED_AR")
fi
exec "${RISCVSIM_PINNED_MAKE:-${RISCVSIM_MAKE:-make}}" -j"${RISCVSIM_MAKE_JOBS:-4}" "${args[@]}"
