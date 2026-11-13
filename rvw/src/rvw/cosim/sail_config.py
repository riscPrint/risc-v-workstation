"""Build a complete Sail 0.15 config and check the model's effective ISA."""
import copy
import json
from pathlib import Path
import re

from rvw.common.proc import run_group


# Keep this list bounded. New instruction extensions need configuration and trace tests.
SINGLE = set("imafdc")
MULTI = {"zicsr", "zifencei", "zicntr", "zihpm", "zba", "zbb", "zbs", "zmmul", "zaamo", "zalrsc",
         "zca", "zcf", "zcd"}
TUNING = {"Sdtrig", "Svade", "Svadu", "Svbare", "Sv32", "Sv39", "Sv48", "Sv57"}
COMMENTS = re.compile(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', re.S)


def read_json(text):
    """Sail's public config is JSON with comments. Keep comment markers inside strings."""
    return json.loads(COMMENTS.sub(lambda m: m[1] or "", text))


def isa_extensions(isa, xlen, *, checked=True):
    match = re.fullmatch(r"rv(32|64)([a-z]+)((?:_[a-z][a-z0-9]*)*)", isa)
    if not match or int(match[1]) != xlen:
        raise ValueError(f"Sail cannot confirm ISA {isa!r}: unsupported ISA spelling or XLEN")
    single = set(match[2])
    multi = set(filter(None, match[3].split("_")))
    if "g" in single:
        single = (single - {"g"}) | set("imafd")
        multi |= {"zicsr", "zifencei"}
    if checked and (single - SINGLE or multi - MULTI or "i" not in single):
        raise ValueError(f"Sail cannot confirm ISA {isa!r}: unsupported extensions")
    extensions = single | multi
    if "m" in extensions:
        extensions.add("zmmul")
    if "a" in extensions:
        extensions |= {"zaamo", "zalrsc"}
    if "c" in extensions:
        extensions.add("zca")
        if "d" in extensions:
            extensions.add("zcd")
        if xlen == 32 and "f" in extensions:
            extensions.add("zcf")
    if ("zca" in extensions and ("d" not in extensions or "zcd" in extensions)
            and (xlen == 64 or "f" not in extensions or "zcf" in extensions)):
        extensions.add("c")  # Sail derives the C alias from its complete component set.
    return extensions


def merge(base, override):
    """Sail's merge rules: a different single-key union replaces its old variant."""
    if isinstance(base, dict) and isinstance(override, dict):
        if len(base) == len(override) == 1 and base.keys() != override.keys():
            return copy.deepcopy(override)
        for key, value in override.items():
            if key not in base:
                raise ValueError(f"Sail config has no setting {key!r}")
            base[key] = merge(base[key], value)
        return base
    if type(base) is not type(override):
        raise ValueError("Sail config override changes a setting's type")
    return copy.deepcopy(override)


def build_config(base, platform, regions, *, custom=False):
    if platform.pmp_granularity != 4 or platform.misaligned["load"] != "trap":
        raise ValueError("Sail cannot implement these PMP-granularity/misaligned platform settings")
    wanted = isa_extensions(platform.sail_reference_isa or platform.reference_isa or platform.isa, platform.xlen)
    c = copy.deepcopy(base)
    if c["base"]["xlen"] != platform.xlen:
        raise ValueError("Sail config XLEN differs from the platform")
    # Start from the config's non-ISA parameters, but no default instruction extensions.
    # Only explicit privileged tuning survives. Privilege support follows the platform.
    tuning = {name: copy.deepcopy(c["extensions"][name]) for name in TUNING} if custom else {}
    c = merge(c, platform.sail_overrides)
    for name in TUNING & platform.sail_overrides.get("extensions", {}).keys():
        tuning[name] = copy.deepcopy(c["extensions"][name])
    mutability = {name: value.get("mutable_misa", False) for name, value in c["extensions"].items()}
    privilege = {name: copy.deepcopy(c["extensions"][name]) for name in ("S", "U")}

    def disable(value):
        if isinstance(value, dict):
            for key in value:
                if key in ("supported", "mutable_misa"):
                    value[key] = False
                else:
                    disable(value[key])
    disable(c["extensions"])
    c["extensions"]["V"].update(support_level="Disabled", vlen_exp=3, elen_exp=3, max_index_eew_exp=3)
    c["base"]["E"] = False
    c["base"]["xlen"] = platform.xlen
    c["base"]["hpmevent_width_bits"] = min(c["base"]["hpmevent_width_bits"], platform.xlen)
    for name, value in privilege.items():
        c["extensions"][name] = dict(value, supported=name in platform.privilege_modes, mutable_misa=False)
    # Remove delegation bits for disabled H, double-trap and software-check extensions.
    if not custom and "medeleg" not in platform.sail_overrides.get("base", {}):
        c["base"]["medeleg"]["delegatable_bits"] = {"len": 64, "value": "0xb3ff"}
    if not custom and "mideleg" not in platform.sail_overrides.get("base", {}):
        c["base"]["mideleg"]["delegatable_bits"] = {"len": "xlen", "value": "0x222"}
    for name in (("Svbare", "Sv32" if platform.xlen == 32 else "Sv39") if "S" in platform.privilege_modes else ()):
        c["extensions"][name]["supported"] = True
    if platform.xlen == 64 and "S" in platform.privilege_modes:
        for name in ("Sv48", "Sv57"):
            c["extensions"][name]["supported"] = True
    for name, value in tuning.items():
        c["extensions"][name] = value
    for name, value in c["extensions"].items():
        if name.lower() in wanted and name not in ("C", "V"):
            value["supported"] = True
            if "mutable_misa" in value:
                value["mutable_misa"] = mutability[name]
    c["extensions"]["C"]["mutable_misa"] = "c" in wanted and mutability["C"]
    if "S" not in platform.privilege_modes:
        c["memory"]["physaddr_bits"] = min(c["memory"]["physaddr_bits"], platform.xlen)
        if "f" not in wanted:
            c["base"]["mstatus"]["fs_legal_states"] = "ExtContext_Off"
        c["base"]["mstatus"]["vs_legal_states"] = "ExtContext_Off"
    # Match Spike's explicit pmpregions and misaligned=false. Sail has fixed CSR-bank sizes.
    c["memory"]["pmp"].update(count=64 if platform.absent_pmp_csrs == "read_zero_write_ignored" else
                               0 if platform.pmp_regions == 0 else 16 if platform.pmp_regions <= 16 else 64,
                               usable_count=platform.pmp_regions)
    c["memory"]["regions"] = regions
    for name in ("load_store", "amo", "lrsc"):
        c["memory"]["misaligned"]["exceptions"][name] = {"Some": "AlignmentException"}
    c["base"]["xtval_nonzero"]["illegal_instruction"] = platform.illegal_insn_tval == "insn"
    return c, wanted


def query(executable, args, timeout, *, env=None):
    result = run_group([str(executable), *args], timeout=timeout, capture=True, **({"env": env} if env is not None else {}))
    if result.timed_out:
        raise ValueError(f"Sail config check did not finish within {timeout} s")
    if result.returncode:
        raise ValueError(f"Sail cannot confirm config: {result.stdout or ''}{result.stderr or ''}")
    return result.stdout or ""


def prepare_config(platform, executable, config, directory, regions, timeout, *, env, default_config):
    def ask(args):
        return query(executable, args, timeout, **({"env": env} if env is not None else {}))
    base = read_json(Path(config).read_text()) if config else read_json(default_config)
    try:
        effective, wanted = build_config(base, platform, regions, custom=config is not None)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Sail cannot confirm config: unsupported config structure ({exc})") from exc
    path = Path(directory) / "effective-config.json"
    path.write_text(json.dumps(effective))
    actual = ask(["--config", str(path), "--print-isa-string"]).strip()
    reported = isa_extensions(actual, platform.xlen, checked=False)
    # Sail advertises privilege and LR/SC capability aliases that are not instruction choices.
    expected = wanted | {name.lower() for name in TUNING - {"Svbare", "Sv32", "Sv39", "Sv48", "Sv57"}
                         if effective["extensions"][name]["supported"]}
    if platform.xlen == 64 and "U" in platform.privilege_modes:
        expected.add("ssu64xl")
    if "zalrsc" in wanted:
        expected |= {"za64rs", "za128rs"}
    if reported != expected:
        raise ValueError(f"Sail effective ISA cannot be confirmed: requested {platform.sail_reference_isa or platform.reference_isa or platform.isa}, "
                         f"reported {actual!r}; missing {sorted(expected - reported)}, extra {sorted(reported - expected)}")
    return path
