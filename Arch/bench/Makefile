# Build single-hart riscv-tests benchmarks with native newlib GCC.
# make SRC=/path/to/riscv-tests/benchmarks BARE_CC=/path/to/riscv64-unknown-elf-gcc
SRC ?=
BARE_CC ?= riscv64-unknown-elf-gcc
BENCHES ?= median qsort rsort towers vvadd memcpy multiply dhrystone spmv
BUILD ?= build/bare
MARCH ?= rv64gc
ABI ?= lp64d
CFLAGS ?= -march=$(MARCH)_zicsr_zifencei -mabi=$(ABI) -mcmodel=medany -O2 -std=gnu99 -ffast-math -fno-common \
          -fno-builtin-printf -fno-tree-loop-distribute-patterns \
          -Wno-implicit-int -Wno-implicit-function-declaration -U_FORTIFY_SOURCE -DPREALLOCATE=1
BARE_FLAGS = -static -nostdlib -nostartfiles -T $(SRC)/common/test.ld

.PHONY: all bare clean check FORCE
all: bare
bare: check $(BENCHES:%=$(BUILD)/%.riscv)

check:
	@test -n "$(SRC)" && test -f "$(SRC)/common/syscalls.c" || \
	  { echo 'Set SRC to riscv-tests/benchmarks' >&2; exit 1; }
	@test -n "$(strip $(BENCHES))" || { echo 'BENCHES must not be empty' >&2; exit 1; }
	@test -n "$(strip $(BUILD))" || { echo 'BUILD must not be empty' >&2; exit 1; }
	@for b in $(BENCHES); do \
	  test -f "micro/$$b.c" || test -d "$(SRC)/$$b" || { echo "Missing benchmark: $$b" >&2; exit 1; }; \
	done

# FORCE also catches a changed SRC, compiler or flags in a reused build dir.
$(BUILD)/syscalls.c: FORCE | check
	@mkdir -p $(@D)
	sh rt/patch_syscalls.sh "$(SRC)/common/syscalls.c" > $@.tmp
	mv $@.tmp $@

$(BUILD)/%.riscv: $(BUILD)/syscalls.c $(wildcard $(SRC)/common/*) FORCE | check
	@mkdir -p $(@D)
	$(BARE_CC) -I$(SRC)/../env -I$(SRC)/common -I$(SRC)/$* $(CFLAGS) $(BARE_FLAGS) \
	  -o $@.tmp $(if $(wildcard micro/$*.c),micro/$*.c,$(wildcard $(SRC)/$*/*.c) $(wildcard $(SRC)/$*/*.S)) \
	  $(BUILD)/syscalls.c $(SRC)/common/crt.S -lm -lgcc
	mv $@.tmp $@

FORCE:
clean:
	rm -rf "$(BUILD)"
