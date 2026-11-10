"""SPICE netlist generation and inspection.

Generation: inject a fitted current pulse into a node of an existing netlist.
Inspection: parse a SPICE deck into a structured summary, used to black-box
compare netlists produced by a reference tool against our own output.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from sfit.tcad import DoubleExp

_FAR = "1"  # second EXP delay [s]: far beyond any transient window


def fmt(x: float) -> str:
    return f"{x:.6g}"


def pulse_source(name: str, node_from: str, node_to: str, p: DoubleExp,
                 style: str = "exp", t_stop: float | None = None, points: int = 200) -> list[str]:
    """SPICE lines for a current pulse flowing from ``node_from`` to ``node_to``.

    style="exp": two standard EXP sources whose sum is the exact double exponential
        A*(1-exp(-t/tau_r)) - A*(1-exp(-t/tau_f)) = A*(exp(-t/tau_f) - exp(-t/tau_r)),
        A = Q/(tau_f - tau_r). Portable across SPICE dialects.
    style="pwl": sampled piecewise-linear waveform.
    """
    a = p.q / (p.tau_f - p.tau_r)
    if style == "exp":
        return [
            f"I{name}r {node_from} {node_to} EXP(0 {fmt(a)} {fmt(p.t0)} {fmt(p.tau_r)} {_FAR} {fmt(p.tau_r)})",
            f"I{name}f {node_from} {node_to} EXP(0 {fmt(-a)} {fmt(p.t0)} {fmt(p.tau_f)} {_FAR} {fmt(p.tau_f)})",
        ]
    if style == "pwl":
        t_end = t_stop if t_stop else p.t0 + 10 * p.tau_f
        t = np.concatenate(([0.0], p.t0 + np.geomspace(p.tau_r / 100, t_end - p.t0, points)))
        t = np.unique(np.concatenate(([0.0, p.t0], t)))
        pairs = " ".join(f"{fmt(tt)} {fmt(ii)}" for tt, ii in zip(t, p.current(t)))
        return [f"I{name} {node_from} {node_to} PWL({pairs})"]
    raise ValueError(f"unknown style: {style}")


def inject(netlist: str, node: str, p: DoubleExp, style: str = "exp",
           t_stop: float | None = None, t_step: float | None = None, ground: str = "0") -> str:
    """Return ``netlist`` with a strike current into ``node`` and a .tran analysis.

    Current is drawn out of ``node`` into ground for positive q (n+ drain collecting
    electrons pulls the node down); use negative q for the opposite polarity.
    """
    t_stop = t_stop or p.t0 + 10 * p.tau_f
    t_step = t_step or min(p.tau_r, t_stop / 1000)
    lines = [ln for ln in netlist.rstrip().splitlines() if ln.strip().lower() != ".end"]
    lines += ["", f"* sfit strike: Q={fmt(p.q)}C tau_r={fmt(p.tau_r)}s tau_f={fmt(p.tau_f)}s"]
    lines += pulse_source("strike", node, ground, p, style=style, t_stop=t_stop)
    if not any(ln.strip().lower().startswith(".tran") for ln in lines):
        lines.append(f".tran {fmt(t_step)} {fmt(t_stop)}")
    lines.append(".end")
    return "\n".join(lines) + "\n"


@dataclass
class Element:
    name: str
    kind: str
    nodes: list[str]
    value: str
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class Deck:
    title: str
    elements: list[Element]
    directives: list[str]
    models: dict[str, str]
    subckts: list[str]

    def summary(self) -> dict:
        nodes = sorted({n for e in self.elements for n in e.nodes})
        return {
            "title": self.title,
            "element_counts": dict(Counter(e.kind for e in self.elements)),
            "nodes": nodes,
            "sources": [vars(e) for e in self.elements if e.kind in "IV"],
            "models": self.models,
            "subckts": self.subckts,
            "directives": self.directives,
        }


_NODE_COUNT = {"R": 2, "C": 2, "L": 2, "V": 2, "I": 2, "D": 2, "Q": 3, "M": 4, "J": 3,
               "E": 4, "G": 4, "F": 2, "H": 2, "B": 2}
_PARAM = re.compile(r"(\w+)\s*=\s*([^\s=]+)")


def parse(text: str) -> Deck:
    """Minimal SPICE parser (continuation lines, comments, elements, .model, .subckt)."""
    raw = text.splitlines()
    title = raw[0].lstrip("* ").strip() if raw else ""
    logical: list[str] = []
    for ln in raw[1:]:
        s = ln.split(";")[0].rstrip()
        if not s.strip() or s.lstrip().startswith("*"):
            continue
        if s.lstrip().startswith("+") and logical:
            logical[-1] += " " + s.lstrip()[1:]
        else:
            logical.append(s.strip())

    elements, directives, models, subckts = [], [], {}, []
    for ln in logical:
        tok = ln.split()
        head = tok[0]
        if head.startswith("."):
            low = head.lower()
            if low == ".model" and len(tok) >= 3:
                models[tok[1]] = " ".join(tok[2:])
            elif low == ".subckt":
                subckts.append(tok[1])
            directives.append(ln)
            continue
        kind = head[0].upper()
        if kind == "X":
            body = [t for t in tok[1:] if "=" not in t]
            nodes, value = body[:-1], body[-1] if body else ""
        else:
            n = _NODE_COUNT.get(kind, 2)
            nodes, value = tok[1:1 + n], " ".join(t for t in tok[1 + n:] if "=" not in t)
        elements.append(Element(head, kind, nodes, value, dict(_PARAM.findall(ln))))
    return Deck(title, elements, directives, models, subckts)


def parse_file(path: str | Path) -> Deck:
    return parse(Path(path).read_text(errors="replace"))
