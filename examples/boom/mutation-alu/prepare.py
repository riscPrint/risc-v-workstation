"""Copy this recipe and one emitted RocketALU to a fresh MCY project."""
import argparse
from pathlib import Path
import re
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("rtl", type=Path)
parser.add_argument("out", type=Path)
args = parser.parse_args()
match = re.search(r"^module RocketALU\s*\(.*?^endmodule", args.rtl.read_text(), re.M | re.S)
if not match:
    parser.error("RTL has no RocketALU module")
args.out.mkdir(parents=True, exist_ok=False)
for name in ("config.mcy", "tb.sv", "test_sim.sh", "check-original.sh", "rvw-external-inputs"):
    shutil.copyfile(Path(__file__).parent / name, args.out / name)
(args.out / "RocketALU.v").write_text(match.group() + "\n")
