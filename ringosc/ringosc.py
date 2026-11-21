#!/usr/bin/env python3
"""Ring oscillator on PTM 45nm with interconnect parasitics: generation, simulation, analysis.

Structure: one NAND2 (enable) followed by N-1 inverters (N odd). Each stage output drives
a wire modeled as a distributed RC ladder of `nseg` pi segments; the wire end connects to
the next stage input. The wire R and C per length come from interconnect.py.

Usage:  python3 ringosc.py            # run all sweeps, write results/ (CSV, PNG, summary)
"""
import csv
import math
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, asdict, replace

import numpy as np

from interconnect import LAYERS

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "pdk", "ptm45", "ptm45.lib")
OUT = os.path.join(HERE, "results")

LMIN = 45e-9
LDIFF = 90e-9  # source/drain diffusion length (for AD/AS/PD/PS -> junction capacitance)


@dataclass(frozen=True)
class Cfg:
    corner: str = "hp"       # hp | lp
    vdd: float = 1.0
    temp: float = 27.0
    nstage: int = 21         # odd
    wn: float = 90e-9
    wp: float = 180e-9
    layer: str = "Mx"
    wire_um: float = 0.0     # wire length per stage [um]
    mcf: float = 1.0         # Miller coupling factor
    wire_r: bool = True      # False: C-only lumped wire (ignore R)
    nseg: int = 0            # pi segments per wire (0 = auto: ~1 per 150 ohm, 1..10)
    enable: bool = True      # False: ring held static (leakage)


def mos(name, d, g, s, b, typ, w, dc=False):
    ad = w * LDIFF
    pd = 2 * (w + LDIFF)
    # dc=True: disable the BSIM4 body-resistor network for the leakage operating point.
    # With rbodymod=1 the DC solver can land on a spurious solution (one device drawing
    # ~170 uA with all node voltages correct). At DC the body current is ~0, so this does
    # not change the leakage physics.
    extra = " rbodymod=0" if dc else ""
    return (f"{name} {d} {g} {s} {b} {typ} W={w:.4g} L={LMIN:.4g} "
            f"AD={ad:.4g} AS={ad:.4g} PD={pd:.4g} PS={pd:.4g}{extra}")


def wire(prefix, a, b, cfg):
    """Distributed RC from node a to node b (pi segments)."""
    lay = LAYERS[cfg.layer]
    length = cfg.wire_um * 1e-6
    if length <= 0:
        return [f"V{prefix} {a} {b} 0"]  # zero-length wire: short
    rt = lay.r() * length
    ct = lay.c_total(cfg.mcf) * length
    if not cfg.wire_r:
        return [f"V{prefix} {a} {b} 0", f"C{prefix} {b} 0 {ct:.5g}"]
    n = cfg.nseg or min(10, max(1, math.ceil(rt / 150.0)))
    lines, nodes = [], [a] + [f"{prefix}_{i}" for i in range(1, n)] + [b]
    for i in range(n):
        lines.append(f"R{prefix}_{i} {nodes[i]} {nodes[i+1]} {rt/n:.5g}")
    # pi: C/2n at both ends of each segment -> interior nodes get C/n, ends C/2n
    for i, nd in enumerate(nodes):
        c = ct / n if 0 < i < n else ct / (2 * n)
        lines.append(f"C{prefix}_{i} {nd} 0 {c:.5g}")
    return lines


def netlist(cfg, tstop, tstep, datafile):
    n = cfg.nstage
    L = [f"* PTM45 ring oscillator {cfg}",
         f'.lib "{LIB}" {cfg.corner}',
         f".temp {cfg.temp}",
         f"VDD vdd 0 {cfg.vdd}"]
    if cfg.enable:
        L.append(f"VEN en 0 PWL(0 0 20p {cfg.vdd})")
    else:
        L.append("VEN en 0 0")
    # stage k: input in{k}, output o{k}; wire o{k} -> in{k+1}
    # stage 0 = NAND2(en, in0); in0 is the wire end from the last stage
    wn2 = 2 * cfg.wn  # series NMOS upsized
    dc = not cfg.enable
    _mos = mos
    mos_ = lambda *a: _mos(*a, dc=dc)
    L += [mos_("MN0a", "o0", "en", "x0", "0", "nch", wn2),
          mos_("MN0b", "x0", "in0", "0", "0", "nch", wn2),
          mos_("MP0a", "o0", "en", "vdd", "vdd", "pch", cfg.wp),
          mos_("MP0b", "o0", "in0", "vdd", "vdd", "pch", cfg.wp)]
    for k in range(1, n):
        L += [mos_(f"MN{k}", f"o{k}", f"in{k}", "0", "0", "nch", cfg.wn),
              mos_(f"MP{k}", f"o{k}", f"in{k}", "vdd", "vdd", "pch", cfg.wp)]
    for k in range(n):
        L += wire(f"w{k}", f"o{k}", f"in{(k + 1) % n}", cfg)
    if cfg.enable:
        L += [".options method=gear reltol=1e-4",
              ".control", f"tran {tstep:.4g} {tstop:.4g}",
              f"wrdata {datafile} v(in1) i(VDD)", ".endc", ".end"]
    else:
        L += [".control", "op", f"print i(VDD) > {datafile}", ".endc", ".end"]
    return "\n".join(L) + "\n"


def run_ngspice(text, workdir):
    path = os.path.join(workdir, "ro.sp")
    with open(path, "w") as f:
        f.write(text)
    env = dict(os.environ, OMP_NUM_THREADS="1")
    r = subprocess.run(["ngspice", "-b", path], cwd=workdir, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError(f"ngspice failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout


def leakage(cfg):
    c = replace(cfg, enable=False)
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "op.txt")
        run_ngspice(netlist(c, 0, 0, out), d)
        txt = open(out).read()
    val = float(txt.split("=")[-1].split()[0])
    return -val * cfg.vdd  # VDD source current is negative when sourcing


def est_period(cfg):
    """Rough Elmore estimate, only used to choose the simulation time."""
    lay = LAYERS[cfg.layer]
    ln = cfg.wire_um * 1e-6
    cw = lay.c_total(cfg.mcf) * ln
    rw = lay.r() * ln if cfg.wire_r else 0
    rdrv = 9e3 * (1.0 / max(cfg.vdd - 0.35, 0.1)) * 0.65 * (90e-9 / cfg.wn)
    if cfg.corner == "lp":
        rdrv *= 4
    cself = 0.6e-15
    td = 0.69 * (rdrv * (cself + cw) + 0.5 * rw * cw)
    return 2 * cfg.nstage * td


def simulate(cfg):
    """Return dict with frequency, power and energy for one configuration."""
    p_leak = leakage(cfg)
    tstop = max(2e-9, 14 * est_period(cfg))
    for _attempt in range(4):
        tstep = tstop / 20000
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "tr.txt")
            run_ngspice(netlist(cfg, tstop, tstep, out), d)
            data = np.loadtxt(out)
        t, v, i = data[:, 0], data[:, 1], -data[:, 3]
        half = cfg.vdd / 2
        idx = np.where((v[:-1] < half) & (v[1:] >= half))[0]
        tc = t[idx] + (half - v[idx]) * (t[idx + 1] - t[idx]) / (v[idx + 1] - v[idx])
        tc = tc[tc > 0.3 * tstop]  # discard start-up
        if len(tc) >= 6:
            break
        tstop *= 3
    else:
        raise RuntimeError(f"no stable oscillation for {cfg}")
    k = len(tc) - 1
    period = (tc[-1] - tc[0]) / k
    m = (t >= tc[0]) & (t <= tc[-1])
    q = np.trapezoid(i[m], t[m])                     # charge drawn over k periods
    p_tot = cfg.vdd * q / (tc[-1] - tc[0])
    vmin, vmax = v[m].min(), v[m].max()
    f = 1 / period
    p_dyn = p_tot - p_leak
    res = asdict(cfg)
    f = float(f); p_tot = float(p_tot); p_dyn = float(p_dyn)
    res.update(freq_GHz=f / 1e9, tstage_ps=period / (2 * cfg.nstage) * 1e12,
               P_total_uW=p_tot * 1e6, P_leak_uW=p_leak * 1e6, P_dyn_uW=p_dyn * 1e6,
               E_cycle_fJ=p_tot / f * 1e15,
               # effective switched capacitance per stage: P_dyn = N * C * V^2 * f
               Ceff_stage_fF=p_dyn / (cfg.nstage * cfg.vdd ** 2 * f) * 1e15,
               swing_V=float(vmax - vmin), periods=k)
    return res


def run_all(cfgs, tag):
    jobs = int(os.environ.get("RO_JOBS", "1"))  # parallel ngspice jobs (1 = sequential)
    if jobs > 1:
        with ProcessPoolExecutor(max_workers=jobs) as ex:
            rows = list(ex.map(simulate, cfgs))
    else:
        rows = [simulate(c) for c in cfgs]
    path = os.path.join(OUT, f"{tag}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[{tag}] {len(rows)} runs -> {os.path.relpath(path, HERE)}")
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    base = Cfg()
    lengths = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500]

    sweeps = {}
    # 1) wire length: distributed RC vs C-only, per layer
    sweeps["length"] = run_all(
        [replace(base, layer=ly, wire_um=l, wire_r=r)
         for ly in ("Mx", "Mg") for r in (True, False) for l in lengths], "sweep_length")
    # 2) supply voltage at 0 / 20 um
    sweeps["vdd"] = run_all(
        [replace(base, vdd=v, wire_um=l) for l in (0, 20)
         for v in (0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2)], "sweep_vdd")
    # 3) temperature at 20 um
    sweeps["temp"] = run_all(
        [replace(base, temp=tt, wire_um=20) for tt in (-40, 0, 27, 85, 125)], "sweep_temp")
    # 4) Miller coupling factor at 20 / 100 um
    sweeps["mcf"] = run_all(
        [replace(base, mcf=m, wire_um=l) for l in (20, 100) for m in (0.0, 1.0, 2.0)], "sweep_mcf")
    # 5) HP vs LP corner
    sweeps["corner"] = run_all(
        [replace(base, corner=c, vdd=v, wire_um=l)
         for c, v in (("hp", 1.0), ("lp", 1.1)) for l in (0, 20, 100)], "sweep_corner")
    plots(sweeps)
    analyze(sweeps)


def plots(s):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def sel(rows, **kw):
        return [r for r in rows if all(r[k] == v for k, v in kw.items())]

    fig, ax = plt.subplots(2, 2, figsize=(11, 8))
    for ly, col in (("Mx", "tab:blue"), ("Mg", "tab:orange")):
        for wr, ls in ((True, "-"), (False, "--")):
            rows = sel(s["length"], layer=ly, wire_r=wr)
            x = [max(r["wire_um"], 0.3) for r in rows]
            lab = f"{ly} {'RC' if wr else 'C only'}"
            ax[0, 0].plot(x, [r["freq_GHz"] for r in rows], ls, color=col, marker="o", ms=3, label=lab)
            ax[0, 1].plot(x, [r["P_total_uW"] for r in rows], ls, color=col, marker="o", ms=3, label=lab)
            ax[1, 0].plot(x, [r["E_cycle_fJ"] for r in rows], ls, color=col, marker="o", ms=3, label=lab)
            ax[1, 1].plot(x, [r["tstage_ps"] for r in rows], ls, color=col, marker="o", ms=3, label=lab)
    for a, yl in zip(ax.flat, ["Frequency [GHz]", "Total power [uW]",
                                "Energy / cycle [fJ]", "Stage delay [ps]"]):
        a.set_xscale("log"); a.set_yscale("log"); a.grid(True, which="both", alpha=.3)
        a.set_xlabel("Wire length per stage [um] (0 plotted at 0.3)"); a.set_ylabel(yl); a.legend(fontsize=8)
    fig.suptitle("PTM45 HP 21-stage RO, 1.0 V, 27C: interconnect length sweep")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "length_sweep.png"), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(1, 3, figsize=(14, 4))
    for l, col in ((0, "tab:blue"), (20, "tab:red")):
        rows = sel(s["vdd"], wire_um=l)
        v = [r["vdd"] for r in rows]
        ax[0].plot(v, [r["freq_GHz"] for r in rows], "o-", color=col, label=f"{l} um")
        ax[1].plot(v, [r["P_dyn_uW"] for r in rows], "o-", color=col, label=f"{l} um dyn")
        ax[1].plot(v, [r["P_leak_uW"] for r in rows], "s--", color=col, label=f"{l} um leak")
        edp = [r["E_cycle_fJ"] * r["tstage_ps"] for r in rows]
        ref = edp[v.index(1.0)]
        ax[2].plot(v, [e / ref for e in edp], "o-", color=col, label=f"{l} um")
    ax[1].set_yscale("log")
    for a, yl in zip(ax, ["Frequency [GHz]", "Power [uW]", "Energy x delay (norm. to 1.0 V)"]):
        a.set_xlabel("VDD [V]"); a.set_ylabel(yl); a.grid(alpha=.3); a.legend(fontsize=8)
    fig.suptitle("Supply voltage sweep (HP, 27C)")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "vdd_sweep.png"), dpi=130); plt.close(fig)

    fig, ax = plt.subplots(1, 3, figsize=(14, 4))
    rows = s["temp"]
    t = [r["temp"] for r in rows]
    ax[0].plot(t, [r["freq_GHz"] for r in rows], "o-", label="freq [GHz]")
    a2 = ax[0].twinx()
    a2.semilogy(t, [r["P_leak_uW"] * 1e3 for r in rows], "s--", color="tab:red", label="leak [nW]")
    ax[0].set_xlabel("Temperature [C]"); ax[0].set_ylabel("Frequency [GHz]"); a2.set_ylabel("Leakage [nW]", color="tab:red")
    ax[0].set_title("Temperature (Mx 20 um)"); ax[0].grid(alpha=.3)
    for l, col in ((20, "tab:blue"), (100, "tab:red")):
        rr = sel(s["mcf"], wire_um=l)
        ax[1].plot([r["mcf"] for r in rr], [r["freq_GHz"] for r in rr], "o-", color=col, label=f"{l} um")
    ax[1].set_xlabel("Miller coupling factor"); ax[1].set_ylabel("Frequency [GHz]"); ax[1].set_yscale("log")
    ax[1].set_title("Crosstalk (neighbour switching)"); ax[1].grid(alpha=.3, which="both"); ax[1].legend()
    for c, col in (("hp", "tab:blue"), ("lp", "tab:green")):
        rr = sel(s["corner"], corner=c)
        ax[2].loglog([r["freq_GHz"] for r in rr], [r["P_total_uW"] for r in rr], "o-", color=col,
                     label=f"{c.upper()} ({rr[0]['vdd']} V)")
        for r in rr:
            ax[2].annotate(f"{r['wire_um']:g}um", (r["freq_GHz"], r["P_total_uW"]), fontsize=7,
                           textcoords="offset points", xytext=(3, 3))
    ax[2].set_xlabel("Frequency [GHz]"); ax[2].set_ylabel("Total power [uW]")
    ax[2].set_title("HP vs LP corner"); ax[2].grid(alpha=.3, which="both"); ax[2].legend()
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "temp_mcf_corner.png"), dpi=130); plt.close(fig)


def analyze(s):
    """Cross-check simulation against first-order theory; write results/summary.txt."""
    lay = LAYERS["Mx"]
    cpm = lay.c_total() * 1e9            # fF/um
    rpm = lay.r() * 1e-6                 # ohm/um
    g = {(r["layer"], r["wire_r"], r["wire_um"]): r for r in s["length"]}
    out = []
    p = out.append
    r0, r500 = g[("Mx", False, 0)], g[("Mx", False, 500)]
    p(f"Mx wire: r = {rpm:.3f} ohm/um, c = {cpm:.4f} fF/um (MCF=1)")
    slope_c = (g[("Mx", True, 500)]["Ceff_stage_fF"] - g[("Mx", True, 0)]["Ceff_stage_fF"]) / 500
    p(f"Ceff slope from P_dyn  = {slope_c:.4f} fF/um  (interconnect model {cpm:.4f})")
    cw = cpm * 500
    sl = (r500["tstage_ps"] - r0["tstage_ps"]) / cw
    reff = sl * 1e-12 / 1e-15 / 0.69
    p(f"delay slope (C-only) = {sl:.3f} ps/fF  ->  Reff(driver, 0.69*R*C) = {reff/1e3:.2f} kohm")
    p(f"intrinsic stage delay (0 um) = {r0['tstage_ps']:.2f} ps, f0 = {r0['freq_GHz']:.3f} GHz")
    p("wire-R penalty (RC - C only) vs Elmore 0.38*Rw*Cw:")
    for ly in ("Mx", "Mg"):
        L_ = LAYERS[ly]
        for l in (20, 100, 200, 500):
            d = g[(ly, True, l)]["tstage_ps"] - g[(ly, False, l)]["tstage_ps"]
            el = 0.38 * L_.r() * l * 1e-6 * L_.c_total() * l * 1e-6 * 1e12
            p(f"  {ly} {l:4d} um: sim {d:7.2f} ps   Elmore {el:7.2f} ps   ({d / g[(ly, True, l)]['tstage_ps'] * 100:4.1f}% of stage delay)")
    pth = 1.0 ** 2 / (2 * 0.69 * reff) * 1e6
    p(f"RO power theory P = V^2/(2*0.69*Reff) = {pth:.1f} uW (sim 69..78 uW, ~independent of load)")
    rows = s["vdd"]
    for l in (0, 20):
        rr = [r for r in rows if r["wire_um"] == l]
        best = min(rr, key=lambda r: r["E_cycle_fJ"] * r["tstage_ps"])
        p(f"min EDP at {l} um: VDD = {best['vdd']} V")
    txt = "\n".join(out)
    print(txt)
    with open(os.path.join(OUT, "summary.txt"), "w") as f:
        f.write(txt + "\n")


def load(tag):
    conv = {"corner": str, "layer": str, "wire_r": lambda x: x == "True", "enable": lambda x: x == "True",
            "nstage": int, "nseg": int, "periods": int}
    with open(os.path.join(OUT, f"{tag}.csv")) as f:
        return [{k: conv.get(k, float)(v) for k, v in r.items()} for r in csv.DictReader(f)]


if __name__ == "__main__":
    if "--analyze-only" in sys.argv:   # re-plot / re-analyze from existing CSVs
        sw = {k: load(f"sweep_{k}") for k in ("length", "vdd", "temp", "mcf", "corner")}
        plots(sw)
        analyze(sw)
    else:
        sys.exit(main())
