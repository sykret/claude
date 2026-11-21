#!/usr/bin/env python3
"""Convert PTM-MG (HSPICE level=72, BSIM-CMG 105.03) model cards to an ngspice OSDI library (model type bsimcmg_va = VA module name).

ngspice loads BSIM-CMG through OSDI (bsimcmg.osdi compiled by OpenVAF from the open
BSIM-CMG 111.0.0 Verilog-A). The cards are rewritten as
    .model nch bsimcmg_va TYPE=1  <params>
    .model pch bsimcmg_va TYPE=-1 <params>
Parameters that do not exist in BSIM-CMG 111.0.0 (HSPICE binning limits lmin/lmax, level,
version, ...) are dropped and listed in the library header so nothing is removed silently.

Usage: python3 tools/convert_ptmmg.py      (run from pdk/ptm)
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VA_PARAMS = os.path.join(ROOT, "osdi", "bsimcmg", "bsimcmg_parameters.include")
MODELS = os.path.join(ROOT, "models")
OUT = os.path.join(ROOT, "ptmmg.lib")

# node: (nominal VDD from the card headers / param.inc)
NODES = {20: 0.9, 16: 0.85, 14: 0.8, 10: 0.75, 7: 0.7}
CORNERS = {"hp": "HP", "lstp": "LSTP"}


def va_params():
    txt = open(VA_PARAMS).read()
    return {m.upper() for m in re.findall(r"`[MBI]P[RI][a-z]{2}\((\w+),", txt)}


def parse_card(path):
    """Return (header comment lines, ordered list of (name, value))."""
    head, pairs = [], []
    for line in open(path):
        s = line.strip()
        if not s:
            continue
        if s.startswith("*"):
            if not pairs and "PTM" in s or "VDD" in s.upper():
                head.append(s.lstrip("* ").strip())
            continue
        if s.lower().startswith(".model"):
            s = s.split(None, 3)[3] if len(s.split(None, 3)) > 3 else ""
        s = s.lstrip("+")
        for name, val in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([-+0-9.eE]+)", s):
            pairs.append((name.upper(), val))
    return head, pairs


def main():
    allowed = va_params()
    out = ["* PTM-MG FinFET models (20/16/14/10/7nm, HP and LSTP) for ngspice via OSDI",
           "* Converted by tools/convert_ptmmg.py from the PTM-MG HSPICE cards (BSIM-CMG 105.03)",
           "* to the open BSIM-CMG 111.0.0 Verilog-A model compiled with OpenVAF (osdi/bsimcmg.osdi).",
           "* Load the model first:   .control / pre_osdi <path>/osdi/bsimcmg.osdi / .endc",
           "* Usage:  .lib \"<path>/ptmmg.lib\" f7hp      devices:  N1 d g s b nch L=11n NFIN=2",
           "* Sections: f20hp f20lstp f16hp f16lstp f14hp f14lstp f10hp f10lstp f7hp f7lstp",
           "* Note: OSDI devices use the instance prefix N (not M)."]
    dropped_all = {}
    for node, vdd in NODES.items():
        for sec, tag in CORNERS.items():
            out += ["", f".lib f{node}{sec}", f"* nominal VDD = {vdd} V"]
            for dev, typ, name in (("nfet", 1, "nch"), ("pfet", -1, "pch")):
                path = os.path.join(MODELS, f"{node}{dev}_{tag}.pm")
                head, pairs = parse_card(path)
                keep, seen = [], set()
                for k, v in pairs:
                    if k in ("TYPE", "LEVEL") or k in seen:
                        continue
                    if k not in allowed:
                        dropped_all.setdefault(k, set()).add(f"{node}{dev}_{tag}")
                        continue
                    seen.add(k)
                    keep.append(f"{k.lower()}={v}")
                out.append(f"* {os.path.basename(path)}: {'; '.join(head[:2])}")
                out.append(f".model {name} bsimcmg_va type={typ}")
                for i in range(0, len(keep), 6):
                    out.append("+ " + " ".join(keep[i:i + 6]))
            out.append(f".endl f{node}{sec}")
    note = ["", "* Parameters dropped (not in BSIM-CMG 111.0.0):"]
    for k in sorted(dropped_all):
        note.append(f"*   {k.lower()}  ({len(dropped_all[k])} cards)")
    open(OUT, "w").write("\n".join(out[:7] + note + out[7:]) + "\n")
    print(f"wrote {OUT}; dropped: {', '.join(sorted(k.lower() for k in dropped_all))}")


if __name__ == "__main__":
    main()
