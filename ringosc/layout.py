#!/usr/bin/env python3
"""Parametric ring-oscillator layout (lambda rules) + simple parasitic extraction.

Every node is drawn with the same simplified SCMOS-style lambda rules (lambda = L/2), so
the layouts are geometrically identical in lambda units and differ only in absolute scale.
Each drawn shape is tagged with its net; extraction turns the tagged M1/M2/poly shapes,
contacts and vias into an R and C per net using the node's interconnect technology
(interconnect.py formulas with node-specific aspect ratio, k and effective resistivity).

Main rules used (lambda):
  poly width 2, poly-poly space 3, poly extension past active 2
  active-active space 3 (4 between cells), contact 2x2, contact-gate 2, active/poly/M1 surround 1
  M1/M2 width 3, space 3, via1 2x2, n-well surround of p-active 6
Simplifications: NMOS W = 4 lambda (= 2L), PMOS W = 8 lambda; one contact on the NMOS and two
on the PMOS diffusion; contacts and vias may be stacked; the enable input is ideal (not extracted).

Usage: python3 layout.py   -> results_nodes/layout/*.gds, *.png, extraction table
"""
import math
import os
from dataclasses import dataclass, field

from interconnect import Layer

HERE = os.path.dirname(os.path.abspath(__file__))

# GDS layer numbers and drawing colours
LAYERS = {  # name: (gds layer, colour, alpha, z-order)
    "nwell":   (1, "#c9e7c3", 0.55, 0),
    "active":  (2, "#3c9a3c", 0.75, 1),
    "nplus":   (3, "#f2d7a6", 0.25, 2),
    "pplus":   (4, "#e8b9d3", 0.25, 2),
    "poly":    (5, "#d62728", 0.80, 3),
    "contact": (6, "#111111", 1.00, 6),
    "metal1":  (7, "#1f77b4", 0.55, 4),
    "via1":    (8, "#555555", 1.00, 7),
    "metal2":  (9, "#ff9f1c", 0.55, 5),
    "fin":     (10, "#6b4f1d", 0.85, 2),
}


@dataclass
class Tech:
    """Process node: device section(s) and interconnect stack assumptions."""
    node: int                 # nm, drawn gate length
    corners: dict             # {"hp": (ngspice section, vdd), ...}
    ar: float                 # metal aspect ratio T/W
    k: float                  # effective dielectric constant
    rho: float                # effective Cu resistivity incl. size effect/barrier [ohm m]
    finfet: bool = False
    lg: float = 0.0           # FinFET gate length [nm] (card L)
    mpitch: float = 0.0       # FinFET M1 pitch [nm]; lambda = mpitch/6
    fpitch: float = 0.0       # fin pitch [nm] (card FPITCH)
    tfin: float = 0.0         # fin width [nm]
    nfin: tuple = (1, 1)      # fins per NMOS / PMOS (p-fin ~0.9x n-fin current -> balanced)

    @property
    def lam(self):            # lambda [m]
        if self.finfet:
            return self.mpitch * 1e-9 / 6
        return self.node * 1e-9 / 2

    @property
    def L(self):              # simulated gate length [m]
        return (self.lg if self.finfet else self.node) * 1e-9

    @property
    def label(self):
        return f"{self.node}nm" + (" FinFET" if self.finfet else "")

    def metal(self, name="M1"):
        w = 3 * self.lam
        return Layer(name, w, w, self.ar * w, self.ar * w, self.k, self.rho)

    def poly(self):
        # silicided poly over STI: 8 ohm/sq, thickness ~ 2 lambda, 6 lambda above substrate
        w, t = 2 * self.lam, 2 * self.lam
        return Layer("poly", w, 3 * self.lam, t, 6 * self.lam, 3.9, 8.0 * t)

    @property
    def r_contact(self):      # ohm per contact (grows as contacts shrink)
        return 10.0 * 180 / self.node

    @property
    def r_via(self):
        return 0.6 * self.r_contact


# ITRS-like interconnect assumptions per node (aspect ratio, k_eff, rho_eff)
TECHS = [
    Tech(180, {"bulk": ("n180", 1.8)},                     1.6, 3.6, 2.2e-8),
    Tech(130, {"bulk": ("n130", 1.3)},                     1.7, 3.3, 2.3e-8),
    Tech(90,  {"bulk": ("n90", 1.2)},                      1.7, 3.0, 2.5e-8),
    Tech(65,  {"bulk": ("n65", 1.1)},                      1.8, 2.9, 2.9e-8),
    Tech(45,  {"hp": ("n45hp", 1.0), "lp": ("n45lp", 1.1)}, 1.8, 2.9, 3.5e-8),
    Tech(32,  {"hp": ("n32hp", 0.9), "lp": ("n32lp", 1.0)}, 1.9, 2.7, 4.3e-8),
    Tech(22,  {"hp": ("n22hp", 0.8), "lp": ("n22lp", 0.95)}, 2.0, 2.55, 5.5e-8),
]
BULK = list(TECHS)

# PTM-MG FinFET nodes. lambda = M1 pitch / 6 (metal pitch 6 lambda in the cell rules), so the
# same cell topology lands near real FinFET cell sizes (7nm inverter ~ 0.11 x 0.25 um).
# M1 pitches are typical foundry values; L, fin pitch and fin width come from the PTM-MG cards.
FINS = [
    Tech(20, {"hp": ("f20hp", 0.9),  "lstp": ("f20lstp", 0.9)},  2.0, 2.55, 5.2e-8, True, 24, 64, 60, 15),
    Tech(16, {"hp": ("f16hp", 0.85), "lstp": ("f16lstp", 0.85)}, 2.0, 2.50, 5.8e-8, True, 20, 64, 42, 12),
    Tech(14, {"hp": ("f14hp", 0.8),  "lstp": ("f14lstp", 0.8)},  2.0, 2.45, 6.3e-8, True, 18, 52, 32, 10),
    Tech(10, {"hp": ("f10hp", 0.75), "lstp": ("f10lstp", 0.75)}, 2.0, 2.40, 7.2e-8, True, 14, 44, 28, 8),
    Tech(7,  {"hp": ("f7hp", 0.7),   "lstp": ("f7lstp", 0.7)},   2.0, 2.35, 8.0e-8, True, 11, 40, 22, 6.5),
]
TECHS = BULK + FINS

WN, WP = 4, 8           # device widths [lambda]
INV_W, NAND_W, CELL_H = 16, 28, 38


@dataclass
class Shape:
    layer: str
    x0: float
    y0: float
    x1: float
    y1: float
    net: str = ""

    def moved(self, dx):
        return Shape(self.layer, self.x0 + dx, self.y0, self.x1 + dx, self.y1, self.net)


@dataclass
class Device:
    name: str
    typ: str              # nch / pch
    d: str
    g: str
    s: str
    w: float              # lambda
    ld: float             # drain diffusion length [lambda]
    ls: float             # source diffusion length [lambda]


@dataclass
class Cell:
    name: str
    width: float
    shapes: list = field(default_factory=list)
    devices: list = field(default_factory=list)

    def r(self, layer, x0, y0, x1, y1, net=""):
        self.shapes.append(Shape(layer, x0, y0, x1, y1, net))


def common(c):
    """Rails, wells and implants shared by all cells."""
    w = c.width
    c.r("metal1", 0, 0, w, 6, "gnd")
    c.r("metal1", 0, 32, w, 38, "vdd")
    c.r("nwell", -1, 15, w + 1, 41)
    c.r("nplus", 0, 3, w, 11)
    c.r("pplus", 0, 19, w, 31)


def inverter():
    """Input on the left poly pad (net 'in'), output M1 strap at x=10..14 (net 'out')."""
    c = Cell("INV", INV_W)
    common(c)
    c.r("active", 2, 5, 14, 9)               # NMOS W=4
    c.r("active", 2, 21, 14, 29)             # PMOS W=8
    c.r("poly", 7, 3, 9, 31, "in")           # gate
    c.r("poly", 2.5, 12, 7.5, 17, "in")      # input pad
    c.r("contact", 4, 13.5, 6, 15.5, "in")
    c.r("metal1", 3, 12.5, 7, 16.5, "in")
    # sources to rails
    c.r("contact", 3, 6, 5, 8, "gnd"); c.r("metal1", 2, 0, 6, 9, "gnd")
    for y in (22, 26):
        c.r("contact", 3, y, 5, y + 2, "vdd")
    c.r("metal1", 2, 21, 6, 38, "vdd")
    # drains -> output strap
    c.r("contact", 11, 6, 13, 8, "out")
    for y in (22, 26):
        c.r("contact", 11, y, 13, y + 2, "out")
    c.r("metal1", 10, 5, 14, 29, "out")
    c.devices = [Device("MN", "nch", "out", "in", "gnd", WN, 5, 5),
                 Device("MP", "pch", "out", "in", "vdd", WP, 5, 5)]
    return c


def nand2():
    """Stage 0: NAND2(fb, en). Left gate = feedback input 'in' (NMOS next to GND),
    right gate = enable. Output collected through M2 from the NMOS drain to the PMOS middle."""
    c = Cell("NAND2", NAND_W)
    common(c)
    c.r("active", 2, 5, 24, 9)
    c.r("active", 2, 21, 24, 29)
    c.r("poly", 7, 3, 9, 31, "in")             # gate A (feedback)
    c.r("poly", 16, 3, 18, 31, "en")           # gate B (enable)
    c.r("poly", 2.5, 12, 7.5, 17, "in")
    c.r("contact", 4, 13.5, 6, 15.5, "in"); c.r("metal1", 3, 12.5, 7, 16.5, "in")
    c.r("poly", 13, 12, 18, 17, "en")
    c.r("contact", 14, 13.5, 16, 15.5, "en"); c.r("metal1", 13, 12.5, 17, 16.5, "en")
    # NMOS: left source to GND, right drain = out (series stack, internal node x)
    c.r("contact", 3, 6, 5, 8, "gnd"); c.r("metal1", 2, 0, 6, 9, "gnd")
    c.r("contact", 21, 6, 23, 8, "out"); c.r("metal1", 20, 5, 24, 16, "out")
    # PMOS: left/right to VDD, middle = out
    for x in (3, 21):
        for y in (22, 26):
            c.r("contact", x, y, x + 2, y + 2, "vdd")
    c.r("metal1", 2, 21, 6, 38, "vdd"); c.r("metal1", 20, 21, 24, 38, "vdd")
    for y in (22, 26):
        c.r("contact", 11.5, y, 13.5, y + 2, "out")
    c.r("metal1", 10.5, 21, 14.5, 29, "out")
    # M2 jumper NMOS drain -> PMOS middle
    c.r("via1", 21, 13, 23, 15, "out")
    c.r("metal2", 20.5, 12.5, 23.5, 20.5, "out")
    c.r("metal2", 11, 17.5, 23.5, 20.5, "out")
    c.r("metal2", 11, 17.5, 14, 24.5, "out")
    c.r("via1", 11.5, 22, 13.5, 24, "out")
    c.devices = [Device("MNA", "nch", "x", "in", "gnd", WN, 7, 5),
                 Device("MNB", "nch", "out", "en", "x", WN, 6, 7),
                 Device("MPA", "pch", "out", "in", "vdd", WP, 7, 5),
                 Device("MPB", "pch", "out", "en", "vdd", WP, 7, 6)]
    return c


@dataclass
class RO:
    tech: Tech
    nstage: int
    shapes: list
    devices: list      # (stage, Device) with nets renamed to global nets
    width: float       # lambda
    height: float

    def area_um2(self):
        return self.width * self.height * (self.tech.lam * 1e6) ** 2


def build_ro(tech, nstage=21):
    """Single-row ring: NAND2 + (nstage-1) inverters, local M1 links, M2 feedback over the row."""
    nets = lambda k: f"n{k % nstage}"       # net n{k} = output of stage k
    shapes, devices = [], []
    x = 0.0
    for k in range(nstage):
        cell = nand2() if k == 0 else inverter()
        ren = {"out": nets(k), "in": nets(k - 1), "en": "en", "gnd": "gnd", "vdd": "vdd",
               "x": f"x{k}", "": ""}
        for s in cell.shapes:
            t = s.moved(x)
            t.net = ren.get(s.net, s.net)
            shapes.append(t)
        for d in cell.devices:
            devices.append((k, Device(f"{d.name}{k}", d.typ, ren[d.d], ren[d.g], ren[d.s],
                                      d.w, d.ld, d.ls)))
        # local link: this output -> next cell's input pad (M1, y 13..16)
        if k < nstage - 1:
            xo = x + (24 if k == 0 else 14)            # right edge of output strap
            xn = x + cell.width + 3                    # next input pad left edge
            shapes.append(Shape("metal1", xo, 13, xn, 16, nets(k)))
        x += cell.width
    if tech.finfet:   # draw fins across each active region at the card fin pitch
        fp, tw = tech.fpitch * 1e-9 / tech.lam, tech.tfin * 1e-9 / tech.lam
        for a in [q for q in shapes if q.layer == "active"]:
            n = tech.nfin[0] if a.y0 < 15 else tech.nfin[1]
            yc = (a.y0 + a.y1) / 2
            for i in range(n):
                y = yc + (i - (n - 1) / 2) * fp
                shapes.append(Shape("fin", a.x0 - 1, y - tw / 2, a.x1 + 1, y + tw / 2))
    # feedback: last output (x_last+10..14) -> M2 track over the VDD rail -> NAND input pad
    xl = x - INV_W
    fb = nets(nstage - 1)
    shapes += [Shape("via1", xl + 11, 26, xl + 13, 28, fb),
               Shape("metal2", xl + 10.5, 25.5, xl + 13.5, 36.5, fb),
               Shape("metal2", 3.5, 33.5, xl + 13.5, 36.5, fb),
               Shape("metal2", 3.5, 12.5, 6.5, 36.5, fb),
               Shape("via1", 4, 13.5, 6, 15.5, fb)]
    return RO(tech, nstage, shapes, devices, x, CELL_H)


# ----------------------------------------------------------------------------- extraction
def extract(ro):
    """Per signal net: list of series segments (R [ohm], C [F]) from driver to load.
    Wires: R = rho_eff*len/(W*T) (sheet resistance for poly), C = per-length model * len.
    Contacts/vias: R each; parallel contacts on the same diffusion are combined."""
    t = ro.tech
    lam = t.lam
    lay = {"metal1": t.metal("M1"), "metal2": t.metal("M2"), "poly": t.poly()}
    nets = {}
    for s in ro.shapes:
        if not s.net.startswith("n"):
            continue
        n = nets.setdefault(s.net, {"wire": [], "nc": 0, "nv": 0, "len": {}})
        w, h = (s.x1 - s.x0) * lam, (s.y1 - s.y0) * lam
        if s.layer in lay:
            L = lay[s.layer]
            length, width = max(w, h), min(w, h)
            if s.layer == "poly" and h > 20 * lam:     # gate finger: subtract the parts over active
                length = h - (WN + WP) * lam
            geo = Layer(L.name, width, L.s, L.t, L.h, L.k, L.rho)
            n["wire"].append((s.layer, length, geo.r() * length, geo.c_total() * length))
            n["len"][s.layer] = n["len"].get(s.layer, 0) + length
        elif s.layer == "contact":
            n["nc"] += 1
        elif s.layer == "via1":
            n["nv"] += 1
    out = {}
    for name, n in nets.items():
        segs = []
        # driver side: drain contacts (N || P groups) ~ one contact R/2, poly contact at the load
        r_ct = t.r_contact * (0.5 + 1.0)
        r_v = t.r_via * n["nv"]
        segs.append(("contact/via", r_ct + r_v, 0.0))
        for layer, length, r, c in n["wire"]:
            segs.append((layer, r, c))
        out[name] = {"segments": segs,
                     "R": sum(s[1] for s in segs), "C": sum(s[2] for s in segs),
                     "len_um": {k: v * 1e6 for k, v in n["len"].items()}}
    return out


# ----------------------------------------------------------------------------- output
def write_gds(ro, path):
    import gdstk
    lib = gdstk.Library(unit=1e-6, precision=1e-9)
    top = lib.new_cell(f"RO{ro.nstage}_{ro.tech.node}nm" + ("_FINFET" if ro.tech.finfet else ""))
    s = ro.tech.lam * 1e6
    for sh in ro.shapes:
        top.add(gdstk.rectangle((sh.x0 * s, sh.y0 * s), (sh.x1 * s, sh.y1 * s),
                                layer=LAYERS[sh.layer][0]))
    top.add(gdstk.Label("EN", (22 * s, 14.5 * s), layer=7))
    lib.write_gds(path)


def draw(ax, shapes, scale=1.0, x0=0.0, labels=True):
    from matplotlib.patches import Rectangle
    for sh in sorted(shapes, key=lambda q: LAYERS[q.layer][3]):
        _, col, a, z = LAYERS[sh.layer]
        ax.add_patch(Rectangle(((sh.x0 - x0) * scale, sh.y0 * scale), (sh.x1 - sh.x0) * scale,
                               (sh.y1 - sh.y0) * scale, facecolor=col, edgecolor=col if a < 1 else "none",
                               lw=0.3, alpha=a, zorder=z))


def figures(outdir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    legend = [Patch(color=LAYERS[k][1], alpha=LAYERS[k][2], label=k) for k in LAYERS]
    # 1) cells in lambda units
    fig, ax = plt.subplots(1, 2, figsize=(10, 6.5), gridspec_kw={"width_ratios": [NAND_W, INV_W + 6]})
    for a, cell in zip(ax, (nand2(), inverter())):
        draw(a, cell.shapes)
        a.set_xlim(-2, cell.width + 2); a.set_ylim(-2, 42); a.set_aspect("equal")
        a.set_title(f"{cell.name}  ({cell.width} x {CELL_H} lambda)")
        a.set_xlabel("x [lambda]"); a.grid(alpha=.2)
    for txt, (xx, yy) in {"GND": (1, 2.2), "VDD": (1, 34.2)}.items():
        ax[1].text(xx, yy, txt, fontsize=8, color="white", weight="bold", zorder=10)
    ax[1].text(4.2, 17.4, "IN", fontsize=8, zorder=10); ax[1].text(10.4, 17.4, "OUT", fontsize=8, zorder=10)
    ax[0].text(3.6, 17.4, "FB", fontsize=8, zorder=10); ax[0].text(13.6, 17.4, "EN", fontsize=8, zorder=10)
    ax[0].set_ylabel("y [lambda]")
    fig.legend(handles=legend, loc="lower center", ncol=9, fontsize=8, frameon=False)
    fig.suptitle("Standard cells (lambda rules, lambda = L/2)")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(os.path.join(outdir, "cells_lambda.png"), dpi=150); plt.close(fig)

    # 2) full ring (45nm) with net highlight
    ro = build_ro([t for t in TECHS if t.node == 45][0])
    fig, ax = plt.subplots(figsize=(14, 2.6))
    draw(ax, ro.shapes, ro.tech.lam * 1e6)
    ax.set_xlim(-0.2, ro.width * ro.tech.lam * 1e6 + 0.2); ax.set_ylim(-0.2, 1.0)
    ax.set_aspect("equal"); ax.set_xlabel("x [um]"); ax.set_ylabel("y [um]")
    ax.set_title(f"21-stage ring oscillator, 45nm ({ro.width * ro.tech.lam * 1e6:.2f} x "
                 f"{ro.height * ro.tech.lam * 1e6:.2f} um): NAND2 enable + 20 INV, M2 feedback over the row")
    fig.tight_layout(); fig.savefig(os.path.join(outdir, "ro_45nm.png"), dpi=170); plt.close(fig)

    # 3) all nodes to the same absolute scale (first 5 stages), stacked in one frame
    from matplotlib.patches import Rectangle as _R
    cut = NAND_W + 4 * INV_W
    fig, ax = plt.subplots(figsize=(11, 6.2))
    y = 0.0
    for t in BULK:
        ro = build_ro(t)
        s = t.lam * 1e6
        sub = [Shape(q.layer, q.x0, q.y0 + y / s, min(q.x1, cut), q.y1 + y / s, q.net)
               for q in ro.shapes if q.x0 < cut and not (q.layer == "metal2" and q.x1 > cut)]
        draw(ax, sub, s)
        ax.text(-0.15, y + CELL_H * s / 2, f"{t.node} nm", ha="right", va="center", fontsize=10)
        ax.text(cut * s + 0.1, y + CELL_H * s / 2,
                f"cell {INV_W*s:.2f} x {CELL_H*s:.2f} um, RO {ro.area_um2():.1f} um2",
                ha="left", va="center", fontsize=8, color="#444")
        y += CELL_H * s + 0.35
    ax.set_xlim(-1.3, cut * TECHS[0].lam * 1e6 + 4.2); ax.set_ylim(-0.3, y)
    ax.set_aspect("equal"); ax.set_yticks([]); ax.set_xlabel("x [um]  (NAND2 + 4 INV of each ring, same scale)")
    ax.set_title("Ring-oscillator layout scaling, 180nm -> 22nm (identical lambda layout)")
    fig.tight_layout(); fig.savefig(os.path.join(outdir, "scaling_same_scale.png"), dpi=160); plt.close(fig)


def fin_figure(outdir):
    """FinFET nodes at one scale + a 7nm inverter close-up showing the fins."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cut = NAND_W + 4 * INV_W
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [2.2, 1]})
    y = 0.0
    for t in FINS:
        ro = build_ro(t)
        s = t.lam * 1e6
        sub = [Shape(q.layer, q.x0, q.y0 + y / s, min(q.x1, cut), q.y1 + y / s, q.net)
               for q in ro.shapes if q.x0 < cut and not (q.layer == "metal2" and q.x1 > cut)]
        draw(ax[0], sub, s)
        ax[0].text(-0.02, y + CELL_H * s / 2, f"{t.node} nm", ha="right", va="center")
        y += CELL_H * s + 0.06
    ax[0].set_xlim(-0.2, cut * FINS[0].lam * 1e6 + 0.05); ax[0].set_ylim(-0.03, y)
    ax[0].set_aspect("equal"); ax[0].set_yticks([]); ax[0].set_xlabel("x [um]")
    ax[0].set_title("FinFET nodes, same scale (NAND2 + 4 INV)")
    t = FINS[-1]
    ro = build_ro(t)
    s = t.lam * 1e9
    x0 = NAND_W
    draw(ax[1], [q for q in ro.shapes if x0 - 1 <= q.x0 < x0 + INV_W], s, x0=x0)
    ax[1].set_xlim(-10, INV_W * s + 10); ax[1].set_ylim(-10, 42 * s); ax[1].set_aspect("equal")
    ax[1].set_xlabel("x [nm]"); ax[1].set_ylabel("y [nm]")
    ax[1].set_title(f"7nm inverter: L={t.lg:g} nm, fin pitch {t.fpitch:g} nm, NFIN n/p = {t.nfin[0]}/{t.nfin[1]}")
    fig.tight_layout(); fig.savefig(os.path.join(outdir, "finfet_layout.png"), dpi=150); plt.close(fig)


def main():
    outdir = os.path.join(HERE, "results_nodes", "layout")
    os.makedirs(outdir, exist_ok=True)
    print(f"{'node':>5} {'area[um2]':>10} {'W x H [um]':>14} {'M1 r[ohm/um]':>12} {'M1 c[fF/um]':>11}"
          f" {'n5 R[ohm]':>9} {'n5 C[fF]':>8} {'fb R[ohm]':>9} {'fb C[fF]':>8} {'fb M2[um]':>9}")
    for t in TECHS:
        ro = build_ro(t)
        write_gds(ro, os.path.join(outdir, f"ro21_{t.node}nm{'_finfet' if t.finfet else ''}.gds"))
        ex = extract(ro)
        m1 = t.metal()
        a, b = ex["n5"], ex[f"n{ro.nstage - 1}"]
        s = t.lam * 1e6
        print(f"{t.node:5d} {ro.area_um2():10.2f} {ro.width*s:6.2f} x {ro.height*s:5.2f} "
              f"{m1.r()*1e-6:12.2f} {m1.c_total()*1e9:11.4f} {a['R']:9.1f} {a['C']*1e15:8.3f} "
              f"{b['R']:9.1f} {b['C']*1e15:8.3f} {b['len_um'].get('metal2', 0):9.2f}")
    figures(outdir)
    fin_figure(outdir)


if __name__ == "__main__":
    main()
