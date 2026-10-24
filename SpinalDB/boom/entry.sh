# Sourced by SpinalDB/build-db.sh for `build-db.sh boom CONFIG OUT.db`. The BOOM-specific settings
# of the design-database build live here, not in the generic tools.
#   $here: the SpinalDB directory; $root: the risc-v-workstation checkout.
# spinal-boom checkout to elaborate (default: the private clone next to the repository).
export SPINAL_BOOM="${SPINAL_BOOM:-$(cd "$root/.." && pwd)/spinal-boom-eda}"
# Compiling the BOOM entry touches that checkout and elaborating BOOM is heavy: hold the machine lock.
LOCK=boom
