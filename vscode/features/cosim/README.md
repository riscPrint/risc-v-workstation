# Cosim mismatch

Open a saved `rvw.cosim/1` report. The webview shows the first divergence, DUT and reference fields, register differences and the raw result. Missing state stays unavailable. Use Jump to Saved ELF Disassembly and select text from `objdump -d` for the run ELF. The command finds the exact PC. It does not run objdump or verify ELF identity. Missing files and missing PCs give a message.
