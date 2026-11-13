# External SoC IP

`rvw soc import-ip DESCRIPTOR --root RTL_ROOT --base ADDRESS --out NEW_DIR`
and MCP `soc_import_ip` use `rvw.soc-ip/1` TOML. The descriptor names the
Verilog module, source files, defines, address/data widths, window size,
address shift, bus signal roles, external ports and register map. Clock and
reset use explicit active-high inputs. Supported buses are APB3 and classic
Wishbone without pipelining. Data widths are 8, 16 or 32 bits. Composer accesses
use full 32-bit words. The descriptor must select the register address shift.

Required roles are clock, reset, address, wdata, rdata, write and ready.
Wishbone adds cycle and strobe. APB3 adds select and enable. Optional roles
are error, irq and byte_select. An absent error is tied to zero. Byte select
is all ones for the declared data width. This profile has no retry, stall,
endianness inference, parameters, bidirectional pins or active-low reset.
Declared external ports have direction in/out and an explicit width.

Register declarations use existing SoC names, offsets, widths, access, reset,
read_action and write_action fields. Missing reset is unknown. Default read
action is none. Default write action is normal. The importer does not infer
register behavior from Verilog or qualify the declared map.

The generated import.json has schema rvw.soc-ip-import/1, a source hash map,
descriptor hash, region, composer binder and generated_only validation.
The source hash map includes expanded include files. Third-party sources are
captured locally in bundle.v. The generated bridge.v and Scala wrapper expose
APB3 for the composer. Missing source files or required bus roles stop import
before output publication. No source download, source edit or test pass is
implied. IP-XACT bus-interface import is outside this TOML profile.
