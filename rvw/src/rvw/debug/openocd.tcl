# Debug 0.13.2: one RV64 hart, abstract GPR/CSR access, mcontrol execute trigger.
# The caller configures and initializes the target before sourcing this file.
proc require_mask {name address mask expected} {
    set value [riscv dmi_read $address]
    if {($value & $mask) != $expected} { error "$name: got $value" }
    echo "RVW_CHECK:$name"
}
proc abstract {reg write value} {
    if {$write} { riscv dmi_write 0x04 $value; riscv dmi_write 0x05 0 }
    riscv dmi_write 0x17 [expr {0x00320000 | ($write << 16) | $reg}]
    for {set i 0} {$i < 100} {incr i} {
        set cs [riscv dmi_read 0x16]
        if {($cs & 0x1000) == 0} { break }
    }
    if {($cs & 0x1700) != 0} { error "abstract command failed: $cs" }
    return [riscv dmi_read 0x04]
}
halt
wait_halt 2000
require_mask halted 0x11 0xf00 0x300
require_mask debug_version 0x11 0xf 2
abstract 0x1008 1 0x1234
if {[abstract 0x1008 0 0] != 0x1234} { error "abstract GPR readback" }
echo "RVW_CHECK:abstract_gpr"
# Observe actual debug entry through dcsr, separately from DM status.
set dcsr [abstract 0x7b0 0 0]
if {(($dcsr >> 6) & 7) == 0} { error "missing debug entry cause" }
echo "RVW_CHECK:debug_cause"
resume
require_mask running 0x11 0xf00 0xc00
halt
wait_halt 2000
require_mask rehalted 0x11 0xf00 0x300
# Invalid command must set cmderr=not supported. Clear sticky cmderr afterwards.
riscv dmi_write 0x17 0xff000000
require_mask unsupported_command 0x16 0x1700 0x200
riscv dmi_write 0x16 0x700
require_mask clear_cmderr 0x16 0x1700 0
# Install one RV64 mcontrol execute trigger, action=Debug Mode, machine privilege.
abstract 0x7a0 1 0
abstract 0x7a2 1 0x80000000
riscv dmi_write 0x04 0x1044
riscv dmi_write 0x05 0x28000000
riscv dmi_write 0x17 0x003307a1
require_mask trigger_command 0x16 0x1700 0
set control [abstract 0x7a1 0 0]
if {($control & 0x1044) != 0x1044} { error "execute trigger not supported" }
# Set DPC to the declared fixture entry, so this test does not need a memory oracle.
abstract 0x7b1 1 0x80000000
resume
wait_halt 2000
set dcsr [abstract 0x7b0 0 0]
if {(($dcsr >> 6) & 7) != 2} { error "trigger did not cause debug entry" }
if {[abstract 0x7b1 0 0] != 0x80000000} { error "trigger stopped at wrong PC" }
echo "RVW_CHECK:execute_trigger"
# Restore trigger slot before returning.
abstract 0x7a1 1 0
echo "RVW_COMPLETE:debug-0.13.2-rv64"
