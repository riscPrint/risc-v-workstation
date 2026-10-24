"""The shared RISC-V decoder (rvw.common.riscv). Words from riscv64-unknown-elf-as -march=rv64gc."""
import pytest

from rvw.common.riscv import classify, decode, integer_sources
from rvw.cov.functional import decode as cov_decode


@pytest.mark.parametrize("word, mnemonic, cls, sources, dest", [
    (0xd0057553, "fcvt.s.w", "float", (("x", 10),), "f"),        # reads an integer register
    (0xf0058053, "fmv.w.x", "float", (("x", 11),), "f"),
    (0xa2b52653, "feq.d", "float", (("f", 10), ("f", 11)), "x"),  # writes an integer register
    (0xc2257553, "fcvt.l.d", "float", (("f", 10),), "x"),
    (0x6ac5f543, "fmadd.d", "float", (("f", 11), ("f", 12), ("f", 13)), "f"),
    (0x20c58553, "fsgnj.s", "float", (("f", 11), ("f", 12)), "f"),
    (0x1005a52f, "lr.w", "atomic", (("x", 11),), "x"),
    (0x02004033, "div", "divide", (("x", 0), ("x", 0)), "x"),
    (0x852e, "c.mv", "alu", (("x", 0), ("x", 11)), "x"),         # add a0, x0, a1
    (0x952e, "c.add", "alu", (("x", 10), ("x", 11)), "x"),
    (0x9002, "c.ebreak", "system", (), "x"),
    (0x40a2, "c.lwsp", "load", (("x", 2),), "x"),
    (0xa001, "c.j", "jump", (), "x"),
])
def test_decode(word, mnemonic, cls, sources, dest):
    d = decode(word)
    assert (d.mnemonic, d.cls, d.sources, d.dest_bank) == (mnemonic, cls, sources, dest)


@pytest.mark.parametrize("word, xlen", [
    (0x0000, 64),        # defined illegal instruction (c.addi4spn with zero immediate)
    (0x8002, 64),        # c.jr x0: reserved
    (0x4002, 64),        # c.lwsp x0: reserved
    (0x66e660e7, 64),    # jalr with funct3 != 0
    (0x653242c7, 64),    # fmsub with fmt 2 (H, not in IMAFDC)
    (0x0000b183 | (3 << 12), 32),  # ld on RV32
    (0x9c01, 32),        # c.subw on RV32
])
def test_reserved_and_other_xlen_encodings_are_unknown(word, xlen):
    assert decode(word, xlen).mnemonic == "unknown" and decode(word, xlen).sources == ()


def test_integer_sources_and_classify():
    assert integer_sources(0x852e) == (0, 11)           # c.mv: rs1 = x0
    assert integer_sources(0x952e) == (10, 11)
    assert integer_sources(0xd0057553) == (10, 0)       # fcvt.s.w
    assert integer_sources(0x6ac5f543) == (0, 0)        # all FP sources
    assert classify(0x02004033) == "muldiv" and classify(0xa001) == "branch" and classify(0x1005a52f) == "amo"
    assert classify(None) == "unknown" and classify(0x0000) == "unknown"


def test_cov_uses_the_shared_decoder():
    # Review finding: three decoders; cov's called fcvt.s.w (reads x10) `unknown`.
    assert cov_decode(0xd0057553) == {"mnemonic": "fcvt.s.w", "class": "float", "uses": [("x", 10)],
                                      "dest_bank": "f", "length": 4}


@pytest.mark.parametrize("base,mnemonic", [(0x0502, "c.slli"), (0x8101, "c.srli"), (0x8501, "c.srai")])
def test_compressed_shift_amounts_by_xlen(base, mnemonic):
    for shamt in range(64):
        word = base | ((shamt & 31) << 2) | ((shamt >> 5) << 12)
        assert decode(word, 64).mnemonic == mnemonic  # shamt=0 is a legal hint
        d = decode(word, 32)
        assert d.mnemonic == ("unknown" if shamt >= 32 else mnemonic)
        if shamt >= 32:
            assert d.sources == () and cov_decode(word, 32)["class"] == "unknown"


@pytest.mark.parametrize("word,rv32,rv64", [
    (0x2001, "c.jal", "unknown"),       # c.addiw rd=0 is reserved on RV64
    (0x2081, "c.jal", "c.addiw"),
    (0x6001, "unknown", "unknown"),    # c.lui immediate=0, including rd=0
    (0x6081, "unknown", "unknown"),
    (0x6101, "unknown", "unknown"),    # c.addi16sp immediate=0
    (0x6005, "c.lui", "c.lui"),        # rd=0, nonzero immediate is a hint
    (0x6185, "c.lui", "c.lui"),
    (0x6141, "c.addi16sp", "c.addi16sp"),
    (0x4002, "unknown", "unknown"),    # c.lwsp rd=0 is reserved
    (0x6002, "c.flwsp", "unknown"),    # FP f0 is valid, integer x0 is reserved
    (0x2002, "c.fldsp", "c.fldsp"),
    (0x9c01, "unknown", "c.subw"),
    (0x9c21, "unknown", "c.addw"),
    (0x9c41, "unknown", "unknown"),
    (0x0002, "c.slli", "c.slli"),      # rd=0, shamt=0 hint
    (0x8002, "unknown", "unknown"),    # c.jr rd=0
])
def test_compressed_reserved_forms_and_hints(word, rv32, rv64):
    assert decode(word, 32).mnemonic == rv32
    assert decode(word, 64).mnemonic == rv64


def test_rv32_reserved_shifts_stay_out_of_coverage_bins(tmp_path):
    import json
    from rvw.cov.functional import functional
    words = [0x1506, 0x9105, 0x9505]
    header = dict(schema="rvw.rvfi/1", xlen=32, isa="rv32imc", core="fixture")
    rows = [dict(order=i, insn=hex(word), mode=3, rd=0, trap=True) for i, word in enumerate(words)]
    trace = tmp_path / "rv32.jsonl"
    trace.write_text("\n".join(map(json.dumps, [header, *rows])) + "\n")
    report = functional([trace])
    assert report["unknown_encodings"] == {hex(word): 1 for word in words}
    assert report["groups"]["mnemonic_mode"]["hits"] == [{"bin": ["unknown", "M"], "count": 3}]


# Round 15: forms with a rounding-mode field named reserved rm values (5, 6) as valid
# instructions; Spike traps `0x003150d3` (fadd.s, rm=5) with cause 2.

def _op_fp(f5, fmt, rs2, rm):
    return (f5 << 27) | (fmt << 25) | (rs2 << 20) | (2 << 15) | (rm << 12) | (1 << 7) | 0x53


RM_FORMS = ([(f"{name}{suffix}", _op_fp(f5, fmt, 3, 0)) for f5, name in enumerate(("fadd", "fsub", "fmul", "fdiv"))
             for fmt, suffix in ((0, ".s"), (1, ".d"))]
            + [(f"fsqrt{s}", _op_fp(11, f, 0, 0)) for f, s in ((0, ".s"), (1, ".d"))]
            + [("fcvt.s.d", _op_fp(8, 0, 1, 0)), ("fcvt.d.s", _op_fp(8, 1, 0, 0))]
            + [(f"fcvt.{i}{s}", _op_fp(24, f, n, 0)) for n, i in enumerate(("w", "wu", "l", "lu"))
               for f, s in ((0, ".s"), (1, ".d"))]
            + [(f"fcvt{s}.{i}", _op_fp(26, f, n, 0)) for n, i in enumerate(("w", "wu", "l", "lu"))
               for f, s in ((0, ".s"), (1, ".d"))]
            + [(f"{name}{s}", (4 << 27) | (f << 25) | (3 << 20) | (2 << 15) | (1 << 7) | op)
               for op, name in ((0x43, "fmadd"), (0x47, "fmsub"), (0x4b, "fnmsub"), (0x4f, "fnmadd"))
               for f, s in ((0, ".s"), (1, ".d"))])


@pytest.mark.parametrize("mnemonic, word", RM_FORMS)
def test_reserved_rounding_modes_are_unknown(mnemonic, word):
    for rm in range(8):
        d = decode(word | rm << 12)
        if rm in (5, 6):
            assert (d.mnemonic, d.sources) == ("unknown", ()), (mnemonic, rm)
        else:   # static modes and DYN (7): a valid encoding (DYN traps only for an invalid frm)
            assert d.mnemonic == mnemonic, (mnemonic, rm, d)


def test_reported_reserved_fadd_is_unknown():
    assert decode(0x003150d3).mnemonic == "unknown" and classify(0x003150d3) == "unknown"
    assert decode(0x003170d3).mnemonic == "fadd.s"      # same word with rm=7 (DYN)


def test_reserved_rounding_mode_stays_out_of_coverage_bins(tmp_path):
    import json
    from rvw.cov.functional import functional
    header = dict(schema="rvw.rvfi/1", xlen=64, isa="rv64imafdc_zicsr", core="fixture", config="t", elf="x")
    row = dict(order=0, cycle=0, pc="0x80000000", pc_next="0x80000004", insn="0x3150d3", mode=3, trap=True,
               intr=False, halt=False, rs1=0, rs1_rdata="0x0", rs2=0, rs2_rdata="0x0", rd=0, rd_wdata="0x0",
               mem_addr="0x0", mem_rmask=0, mem_wmask=0, mem_rdata="0x0", mem_wdata="0x0", mem_fault=False)
    trace = tmp_path / "t.jsonl"
    trace.write_text(json.dumps(header) + "\n" + json.dumps(row) + "\n")
    report = functional([trace])
    bins = [h["bin"][0] for h in report["groups"]["mnemonic_mode"]["hits"]]
    assert "fadd.s" not in bins and bins == ["unknown"], bins
    assert report["unknown_encodings"] == {"0x3150d3": 1}


@pytest.mark.parametrize("word,xlen", [
    (_op_fp(11, 0, 1, 0), 64),  # fsqrt requires rs2=0
    (_op_fp(8, 0, 0, 0), 64),   # fcvt.s.s is reserved
    (_op_fp(8, 1, 1, 0), 64),   # fcvt.d.d is reserved
    (_op_fp(24, 0, 4, 0), 64),  # integer conversion selector out of range
    (_op_fp(26, 1, 4, 0), 64),
    (_op_fp(24, 0, 2, 7), 32),  # long integer conversion requires RV64
    (_op_fp(26, 1, 3, 7), 32),
    (_op_fp(4, 0, 3, 3), 64),   # fsgnj funct3 is not rm
    (_op_fp(5, 1, 3, 2), 64),   # fmin/fmax funct3 is not rm
    (_op_fp(20, 0, 3, 3), 64),  # compare funct3 is not rm
    (_op_fp(28, 0, 1, 0), 64),  # fmv/fclass requires rs2=0
    (_op_fp(28, 1, 1, 1), 64),
    (_op_fp(28, 0, 0, 7), 64),  # fmv/fclass does not accept DYN
    (_op_fp(30, 0, 0, 7), 64),
    (_op_fp(28, 1, 0, 0), 32),  # fmv.x.d requires RV64
    (_op_fp(30, 1, 0, 0), 32),
    (_op_fp(0, 2, 3, 0), 64),   # half/quad not in this decoder's IMAFDC scope
    (_op_fp(0, 3, 3, 0), 64),
])
def test_other_reserved_fp_fields_are_unknown(word, xlen):
    assert decode(word, xlen).mnemonic == "unknown"
    assert decode(word, xlen).sources == ()


def test_decoder_consumers_keep_valid_fp_sources_and_classes():
    from rvw.common.riscv import classify as bundle_classify
    from rvw.common.riscv import integer_sources as cosim_sources

    for word, cls, sources in [(0xd0057553, "fp", (10, 0)),  # fcvt.s.w with DYN
                               (0xd0055553, "unknown", (0, 0))]:  # same form with rm=5
        assert bundle_classify(word) == cls
        assert cosim_sources(word) == sources
