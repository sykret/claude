#!/usr/bin/env python3
"""21-stage ring oscillator across PTM nodes (180nm..22nm) with layout-extracted parasitics.

For every node/corner four configurations are simulated:
  intrinsic : devices only (drain/source areas from the layout), no wire RC
  layout    : + parasitic RC of every net extracted from the layout (layout.py)
  wire10    : layout + an extra 10 um intermediate-metal wire per stage (distributed RC)
  wire100   : layout + an extra 100 um wire per stage

Usage: python3 multinode.py            # simulate + plots + summary  (~5-10 min sequential)
       python3 multinode.py --analyze-only
"""
import csv
import math
import os
import subprocess
import sys
import tempfile

import numpy as np

from layout import TECHS, build_ro, extract

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "pdk", "ptm", "ptm.lib"))
OUT = os.path.join(HERE, "results_nodes")
CONFIGS = ("intrinsic", "layout", "wire10", "wire100")


def pi_chain(prefix, a, b, segs):
    """Series of (R, C) segments a -> b, each a pi section; long segments split."""
    lines, nodes = [], [a]
    flat = []
    for r, c, nsplit in segs:
        for _ in range(nsplit):
            flat.append((r / nsplit, c / nsplit))
    for i, (r, c) in enumerate(flat):
        nxt = b if i == len(flat) - 1 else f"{prefix}_{i}"
        lines.append(f"R{prefix}_{i} {nodes[-1]} {nxt} {max(r, 1e-3):.5g}")
        if c > 0:
            lines.append(f"C{prefix}_{i}a {nodes[-1]} 0 {c/2:.5g}")
            lines.append(f"C{prefix}_{i}b {nxt} 0 {c/2:.5g}")
        nodes.append(nxt)
    return lines


def netlist(tech, corner, config, mode, datafile, tstop=0.0):
    sec, vdd = tech.corners[corner]
    ro = build_ro(tech)
    lam = tech.lam
    bsim4 = tech.node != 180
    L = [f"* RO21 {tech.node}nm {corner} {config} {mode}", f'.lib "{LIB}" {sec}',
         f"VDD vdd 0 {vdd}",
         f"VEN en 0 PWL(0 0 20p {vdd})" if mode == "tran" else "VEN en 0 0"]
    extra = " rbodymod=0" if (mode == "op" and bsim4) else ""
    for k, d in ro.devices:
        w = d.w * lam
        ad, as_ = w * d.ld * lam, w * d.ls * lam
        pd, ps = 2 * (w + d.ld * lam), 2 * (w + d.ls * lam)
        g = f"{d.g}_l" if d.g.startswith("n") else d.g
        b = "0" if d.typ == "nch" else "vdd"
        L.append(f"{d.name} {d.d} {g} {d.s} {b} {d.typ} W={w:.4g} L={tech.node}n "
                 f"AD={ad:.4g} AS={as_:.4g} PD={pd:.4g} PS={ps:.4g}{extra}")
    ex = extract(ro)
    wire = tech.metal("M2")
    for k in range(ro.nstage):
        net = f"n{k}"
        segs = []
        if config != "intrinsic":
            order = {"contact/via": 0, "metal1": 1, "metal2": 1, "poly": 2}
            for layer, r, c in sorted(ex[net]["segments"], key=lambda s: order[s[0]]):
                n = 1
                if layer == "metal2":
                    n = min(10, max(1, math.ceil(c / 0.5e-15)))
                segs.append((r, c, n))
        if config.startswith("wire"):
            ln = float(config[4:]) * 1e-6
            rw, cw = wire.r() * ln, wire.c_total() * ln
            segs.insert(1, (rw, cw, min(10, max(2, math.ceil(rw / 150)))))
        if segs:
            L += pi_chain(f"w{k}", net, f"{net}_l", segs)
        else:
            L.append(f"Vw{k} {net} {net}_l 0")
    if mode == "tran":
        L += [".options method=gear reltol=1e-4", ".control",
              f"tran {tstop/20000:.4g} {tstop:.4g}", f"wrdata {datafile} v(n1) i(VDD)", ".endc", ".end"]
    else:
        L += [".control", "op", f"print i(VDD) > {datafile}", ".endc", ".end"]
    return "\n".join(L) + "\n"


def ngspice(text, d):
    p = os.path.join(d, "ro.sp")
    open(p, "w").write(text)
    r = subprocess.run(["ngspice", "-b", p], cwd=d, capture_output=True, text=True,
                       env=dict(os.environ, OMP_NUM_THREADS="1"))
    if r.returncode != 0:
        raise RuntimeError(r.stdout[-1500:] + r.stderr[-1500:])


def simulate(tech, corner, config):
    sec, vdd = tech.corners[corner]
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "op.txt")
        ngspice(netlist(tech, corner, config, "op", f), d)
        p_leak = -float(open(f).read().split("=")[-1].split()[0]) * vdd
    # initial guess of the simulated time; extended automatically if too short
    tstop = 1.5e-9 * (tech.node / 45) * (4 if corner == "lp" else 1)
    if config == "wire10":
        tstop *= 3
    if config == "wire100":
        tstop *= 20
    for _ in range(6):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "tr.txt")
            ngspice(netlist(tech, corner, config, "tran", f, tstop), d)
            data = np.loadtxt(f)
        t, v, i = data[:, 0], data[:, 1], -data[:, 3]
        h = vdd / 2
        idx = np.where((v[:-1] < h) & (v[1:] >= h))[0]
        tc = t[idx] + (h - v[idx]) * (t[idx + 1] - t[idx]) / (v[idx + 1] - v[idx])
        tc = tc[tc > 0.3 * tstop]
        if len(tc) >= 6:
            break
        tstop *= 3 if len(tc) >= 2 else 6
    else:
        raise RuntimeError(f"no oscillation: {tech.node} {corner} {config}")
    k = len(tc) - 1
    T = (tc[-1] - tc[0]) / k
    m = (t >= tc[0]) & (t <= tc[-1])
    p_tot = float(vdd * np.trapezoid(i[m], t[m]) / (tc[-1] - tc[0]))
    fr = 1 / T
    ro = build_ro(tech)
    ex = extract(ro)
    return dict(node=tech.node, corner=corner, config=config, vdd=vdd,
                freq_GHz=fr / 1e9, tstage_ps=T / 42 * 1e12,
                P_total_uW=p_tot * 1e6, P_leak_uW=p_leak * 1e6,
                leak_pct=p_leak / p_tot * 100,
                E_cycle_fJ=p_tot / fr * 1e15,
                Ceff_stage_fF=(p_tot - p_leak) / (21 * vdd ** 2 * fr) * 1e15,
                area_um2=ro.area_um2(),
                C_wire_local_fF=ex["n5"]["C"] * 1e15, R_wire_local=ex["n5"]["R"],
                C_wire_fb_fF=ex["n20"]["C"] * 1e15, R_wire_fb=ex["n20"]["R"],
                periods=k)


def run():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for t in TECHS:
        for corner in t.corners:
            for cfg in CONFIGS:
                r = simulate(t, corner, cfg)
                rows.append(r)
                print(f"{t.node:4d} {corner:4s} {cfg:9s} f={r['freq_GHz']:8.4f} GHz  P={r['P_total_uW']:8.2f} uW "
                      f"E={r['E_cycle_fJ']:8.2f} fJ  leak={r['P_leak_uW']*1e3:9.2f} nW", flush=True)
    with open(os.path.join(OUT, "nodes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    return rows


def load():
    with open(os.path.join(OUT, "nodes.csv")) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in r.items():
            if k not in ("corner", "config"):
                r[k] = float(v)
    return rows


def plots(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def series(corner_pick, cfg, key):
        xs, ys = [], []
        for t in TECHS:
            c = corner_pick(t)
            if c is None:
                continue
            r = [q for q in rows if q["node"] == t.node and q["corner"] == c and q["config"] == cfg]
            if r:
                xs.append(t.node); ys.append(r[0][key])
        return xs, ys

    hp = lambda t: "bulk" if "bulk" in t.corners else "hp"
    lp = lambda t: "lp" if "lp" in t.corners else None
    sty = {"intrinsic": ("tab:gray", ":"), "layout": ("tab:blue", "-"),
           "wire10": ("tab:orange", "--"), "wire100": ("tab:red", "-.")}

    fig, ax = plt.subplots(2, 3, figsize=(15, 8.5))
    panels = [("freq_GHz", "Frequency [GHz]", True), ("tstage_ps", "Stage delay [ps]", True),
              ("P_total_uW", "Total power [uW]", True), ("E_cycle_fJ", "Energy / cycle [fJ]", True),
              ("P_leak_uW", "Leakage power [uW]", True), ("leak_pct", "Leakage share of total [%]", True)]
    for a, (key, lab, logy) in zip(ax.flat, panels):
        for cfg in CONFIGS:
            col, ls = sty[cfg]
            x, y = series(hp, cfg, key)
            a.plot(x, y, ls, color=col, marker="o", ms=4, label=f"{cfg} (bulk/HP)")
            x, y = series(lp, cfg, key)
            if x and cfg in ("layout", "wire100"):
                a.plot(x, y, ls, color=col, marker="s", ms=4, mfc="white", label=f"{cfg} (LP)")
        a.set_xscale("log"); a.set_xticks([t.node for t in TECHS]); a.set_xticklabels([t.node for t in TECHS])
        a.invert_xaxis()
        if logy:
            a.set_yscale("log")
        a.set_xlabel("Technology node [nm]"); a.set_ylabel(lab); a.grid(alpha=.3, which="both")
    ax[0, 0].legend(fontsize=7, ncol=2)
    fig.suptitle("PTM 21-stage RO across nodes: intrinsic vs layout-extracted vs extra wire (nominal VDD, 27C)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "nodes_overview.png"), dpi=130); plt.close(fig)

    # wire impact: frequency loss vs intrinsic
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.3))
    for cfg in ("layout", "wire10", "wire100"):
        col, ls = sty[cfg]
        x, y = series(hp, cfg, "freq_GHz")
        _, y0 = series(hp, "intrinsic", "freq_GHz")
        ax[0].plot(x, [100 * (1 - a / b) for a, b in zip(y, y0)], ls, color=col, marker="o", label=cfg)
        _, e = series(hp, cfg, "E_cycle_fJ")
        _, e0 = series(hp, "intrinsic", "E_cycle_fJ")
        ax[1].plot(x, [a / b for a, b in zip(e, e0)], ls, color=col, marker="o", label=cfg)
    for a, lab in zip(ax, ["Frequency loss vs intrinsic [%]", "Energy/cycle relative to intrinsic [x]"]):
        a.set_xscale("log"); a.set_xticks([t.node for t in TECHS]); a.set_xticklabels([t.node for t in TECHS])
        a.invert_xaxis(); a.set_xlabel("Technology node [nm]"); a.set_ylabel(lab); a.grid(alpha=.3); a.legend()
    ax[1].set_yscale("log")
    fig.suptitle("Interconnect impact grows with scaling (bulk/HP corners)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "wire_impact.png"), dpi=130); plt.close(fig)


def summary(rows):
    def g(node, corner, cfg):
        return [r for r in rows if r["node"] == node and r["corner"] == corner and r["config"] == cfg][0]
    lines = ["node corner  VDD  f_int[GHz] f_lay[GHz] loss%  f_w10  f_w100  P_lay[uW] E_lay[fJ] "
             "leak[nW] leak%  area[um2]"]
    for t in TECHS:
        for c in t.corners:
            a, b, w1, w2 = (g(t.node, c, x) for x in CONFIGS)
            lines.append(f"{t.node:4d} {c:6s} {a['vdd']:4.2f} {a['freq_GHz']:10.3f} {b['freq_GHz']:10.3f} "
                         f"{100*(1-b['freq_GHz']/a['freq_GHz']):5.1f} {w1['freq_GHz']:6.3f} {w2['freq_GHz']:7.4f} "
                         f"{b['P_total_uW']:9.1f} {b['E_cycle_fJ']:9.2f} {b['P_leak_uW']*1e3:8.2f} "
                         f"{b['leak_pct']:5.2f} {b['area_um2']:9.2f}")
    txt = "\n".join(lines)
    print(txt)
    open(os.path.join(OUT, "summary.txt"), "w").write(txt + "\n")


if __name__ == "__main__":
    rows = load() if "--analyze-only" in sys.argv else run()
    plots(rows)
    summary(rows)
