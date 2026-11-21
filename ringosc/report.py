#!/usr/bin/env python3
"""Build the HTML report (layouts as inline SVG from layout.py, charts from results_nodes/nodes.csv)."""
import html
import math
import os

from layout import TECHS, BULK, FINS, LAYERS, CELL_H, INV_W, NAND_W, build_ro, extract, inverter, nand2
from multinode import load

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "report", "index.html")

rows = load()
G = lambda n, c, k: [r for r in rows if r["node"] == n and r["corner"] == c and r["config"] == k][0]
MAIN = lambda t: "bulk" if "bulk" in t.corners else "hp"
LPC = lambda t: "lp" if "lp" in t.corners else ("lstp" if "lstp" in t.corners else None)
NLAB = lambda t: f"<b>{t.node}</b>" + (" <small>FinFET</small>" if t.finfet else "")
NODES = [t.node for t in TECHS]
CFG_LABEL = {"intrinsic": "소자만 (배선 없음)", "layout": "레이아웃 추출", "wire10": "+10 µm 배선/단",
             "wire100": "+100 µm 배선/단"}


def fmt(v, d=3):
    if v == 0:
        return "0"
    if abs(v) >= 100:
        return f"{v:,.0f}"
    if abs(v) >= 10:
        return f"{v:.1f}"
    return f"{v:.{d}g}"


# ------------------------------------------------------------------ layout SVG
def layout_svg(shapes, x0, x1, y0, y1, scale, title, labels=(), height_px=None, grid=None):
    w, h = (x1 - x0) * scale, (y1 - y0) * scale
    order = sorted(shapes, key=lambda s: LAYERS[s.layer][3])
    out = [f'<svg viewBox="0 0 {w:.2f} {h:.2f}" role="img" aria-label="{html.escape(title)}" '
           f'class="lay" preserveAspectRatio="xMinYMin meet"'
           + (f' style="max-height:{height_px}px"' if height_px else "") + ">"]
    out.append(f'<rect x="0" y="0" width="{w:.2f}" height="{h:.2f}" class="lay-bg"/>')
    if grid:
        gx = x0 + (-x0 % grid)
        while gx <= x1:
            X = (gx - x0) * scale
            out.append(f'<line x1="{X:.2f}" y1="0" x2="{X:.2f}" y2="{h:.2f}" class="lay-grid"/>')
            gx += grid
        gy = y0 + (-y0 % grid)
        while gy <= y1:
            Y = h - (gy - y0) * scale
            out.append(f'<line x1="0" y1="{Y:.2f}" x2="{w:.2f}" y2="{Y:.2f}" class="lay-grid"/>')
            gy += grid
    for s in order:
        X = (s.x0 - x0) * scale
        Y = h - (s.y1 - y0) * scale
        out.append(f'<rect x="{X:.2f}" y="{Y:.2f}" width="{(s.x1-s.x0)*scale:.2f}" '
                   f'height="{(s.y1-s.y0)*scale:.2f}" class="L-{s.layer}"/>')
    for (tx, ty, txt) in labels:
        out.append(f'<text x="{(tx-x0)*scale:.2f}" y="{h-(ty-y0)*scale:.2f}" class="lay-lbl">{html.escape(txt)}</text>')
    out.append("</svg>")
    return "".join(out)


def legend_layers():
    items = []
    names = {"nwell": "N-well", "active": "Active", "nplus": "N+ implant", "pplus": "P+ implant",
             "poly": "Poly", "contact": "Contact", "metal1": "Metal1", "via1": "Via1", "metal2": "Metal2", "fin": "Fin"}
    for k in LAYERS:
        items.append(f'<span class="lg"><svg width="14" height="14" aria-hidden="true">'
                     f'<rect width="14" height="14" class="L-{k}"/></svg>{names[k]}</span>')
    return '<div class="legend">' + "".join(items) + "</div>"


def cells_figure():
    inv, nd = inverter(), nand2()
    s = 7.0
    a = layout_svg(nd.shapes, -1, NAND_W + 1, -1, 42, s, "NAND2 cell", grid=5,
                   labels=[(3.2, 18, "FB"), (13, 18, "EN"), (19.6, 10.5, "OUT")])
    b = layout_svg(inv.shapes, -1, INV_W + 1, -1, 42, s, "Inverter cell", grid=5,
                   labels=[(3, 18, "IN"), (10, 18, "OUT"), (6.6, 34.4, "VDD"), (6.6, 2.4, "GND")])
    return (f'<div class="cells"><figure><div class="svgwrap">{a}</div><figcaption>NAND2 (enable 단) '
            f'— {NAND_W} × {CELL_H} λ</figcaption></figure><figure><div class="svgwrap">{b}</div>'
            f'<figcaption>인버터 — {INV_W} × {CELL_H} λ, Wn = 4λ (2L), Wp = 8λ</figcaption></figure></div>')


def ro_figure(node=45):
    t = [q for q in TECHS if q.node == node][0]
    ro = build_ro(t)
    s = 3.2
    svg = layout_svg(ro.shapes, -1, ro.width + 1, -1, 42, s, f"{node}nm ring oscillator")
    um = t.lam * 1e6
    return (f'<figure class="wide"><div class="svgwrap scroll">{svg}</div><figcaption>{node}nm 21단 링 오실레이터 전체 '
            f'({ro.width*um:.2f} × {ro.height*um:.2f} µm). 각 단 출력은 M1으로 다음 단 입력 패드에 연결되고, '
            f'마지막 단 출력은 VDD 레일 위를 지나는 M2 트랙으로 첫 단(NAND2)에 되돌아갑니다.</figcaption></figure>')


def scaling_figure():
    cut = NAND_W + 4 * INV_W
    s = 46.0  # px per um
    parts, y = [], 0.0
    gap = 0.35
    W = cut * BULK[0].lam * 1e6
    total_h = sum(CELL_H * t.lam * 1e6 + gap for t in BULK)
    for t in BULK:
        ro = build_ro(t)
        um = t.lam * 1e6
        sub = [q for q in ro.shapes if q.x0 < cut and not (q.layer == "metal2" and q.x1 > cut)]
        for q in sorted(sub, key=lambda q: LAYERS[q.layer][3]):
            X = q.x0 * um * s
            Y = (total_h - y - q.y1 * um) * s
            parts.append(f'<rect x="{X+90:.2f}" y="{Y:.2f}" width="{(min(q.x1, cut)-q.x0)*um*s:.2f}" '
                         f'height="{(q.y1-q.y0)*um*s:.2f}" class="L-{q.layer}"/>')
        cy = (total_h - y - CELL_H * um / 2) * s
        parts.append(f'<text x="80" y="{cy+5:.1f}" class="lay-node" text-anchor="end">{t.node} nm</text>')
        parts.append(f'<text x="{90 + cut*um*s + 12:.1f}" y="{cy+5:.1f}" class="lay-note">'
                     f'RO {ro.area_um2():.1f} µm²  ·  셀 {INV_W*um:.2f} × {CELL_H*um:.2f} µm</text>')
        y += CELL_H * um + gap
    wpx, hpx = 90 + W * s + 330, total_h * s + 30
    # 1 um scale bar
    parts.append(f'<line x1="90" y1="{hpx-12}" x2="{90+s}" y2="{hpx-12}" class="lay-scale"/>'
                 f'<text x="{90+s+8}" y="{hpx-7}" class="lay-note">1 µm</text>')
    svg = (f'<svg viewBox="0 0 {wpx:.1f} {hpx:.1f}" class="lay" role="img" '
           f'aria-label="같은 축척의 노드별 레이아웃">' + "".join(parts) + "</svg>")
    return (f'<figure class="wide"><div class="svgwrap scroll">{svg}</div><figcaption>모든 노드를 같은 축척으로 '
            f'그린 링 오실레이터 앞부분(NAND2 + 인버터 4개). λ 단위로는 동일한 레이아웃이므로 면적은 노드² 에 비례해 '
            f'180nm → 22nm 에서 {build_ro(BULK[0]).area_um2()/build_ro(BULK[-1]).area_um2():.0f}배 줄어듭니다.'
            f'</figcaption></figure>')


def finfet_figures():
    """FinFET rows at one scale, and a 7nm inverter close-up in nm showing the fins."""
    cut = NAND_W + 4 * INV_W
    s = 520.0  # px per um
    parts, y, gap = [], 0.0, 0.05
    total_h = sum(CELL_H * t.lam * 1e6 + gap for t in FINS)
    W = cut * FINS[0].lam * 1e6
    for t in FINS:
        ro = build_ro(t)
        um = t.lam * 1e6
        sub = [q for q in ro.shapes if q.x0 < cut and not (q.layer == "metal2" and q.x1 > cut)]
        for q in sorted(sub, key=lambda q: LAYERS[q.layer][3]):
            X = q.x0 * um * s
            Y = (total_h - y - q.y1 * um) * s
            parts.append(f'<rect x="{X+90:.2f}" y="{Y:.2f}" width="{(min(q.x1, cut)-q.x0)*um*s:.2f}" '
                         f'height="{(q.y1-q.y0)*um*s:.2f}" class="L-{q.layer}"/>')
        cy = (total_h - y - CELL_H * um / 2) * s
        parts.append(f'<text x="80" y="{cy+5:.1f}" class="lay-node" text-anchor="end">{t.node} nm</text>')
        parts.append(f'<text x="{90 + cut*um*s + 12:.1f}" y="{cy+5:.1f}" class="lay-note">'
                     f'RO {ro.area_um2():.2f} µm²  ·  M1 pitch {t.mpitch:g} nm  ·  fin pitch {t.fpitch:g} nm</text>')
        y += CELL_H * um + gap
    wpx, hpx = 90 + W * s + 400, total_h * s + 30
    parts.append(f'<line x1="90" y1="{hpx-12}" x2="{90+0.1*s}" y2="{hpx-12}" class="lay-scale"/>'
                 f'<text x="{90+0.1*s+8}" y="{hpx-7}" class="lay-note">100 nm</text>')
    rows = (f'<svg viewBox="0 0 {wpx:.1f} {hpx:.1f}" class="lay" role="img" aria-label="FinFET 노드 레이아웃">'
            + "".join(parts) + "</svg>")
    t = FINS[-1]
    ro = build_ro(t)
    x0 = NAND_W
    cell = [q for q in ro.shapes if x0 - 1 <= q.x0 < x0 + INV_W]
    nm = t.lam * 1e9
    close = layout_svg(cell, x0 - 1, x0 + INV_W + 1, -1, 42, 7.0, "7nm inverter with fins", grid=None,
                       labels=[(x0 + 3, 18, "IN"), (x0 + 10, 18, "OUT")])
    return (f'<div class="cells"><figure><div class="svgwrap scroll">{rows}</div><figcaption>FinFET 5개 노드를 같은 축척으로 '
            f'그린 링 오실레이터 앞부분. λ = M1 pitch / 6 이라 20nm 와 16nm 는 같은 64 nm 금속 피치를 써 크기가 같습니다.'
            f'</figcaption></figure><figure><div class="svgwrap">{close}</div><figcaption>7nm 인버터 확대: '
            f'셀 {INV_W*nm:.0f} × {CELL_H*nm:.0f} nm, L = {t.lg:g} nm, 핀 폭 {t.tfin:g} nm, 핀 피치 {t.fpitch:g} nm, '
            f'NMOS/PMOS 각 {t.nfin[0]} fin (갈색 가로선).</figcaption></figure></div>')


# ------------------------------------------------------------------ charts
def log_ticks(lo, hi):
    ticks = []
    e = math.floor(math.log10(lo))
    while 10 ** e <= hi * 1.0001:
        for m in (1, 2, 5):
            v = m * 10 ** e
            if lo * 0.999 <= v <= hi * 1.001:
                ticks.append(v)
        e += 1
    return ticks


def line_chart(cid, title, series, ylabel, logy=True, ymin=None, ymax=None, unit="", height=300):
    """series: list of dict(name, cls, marker, pts=[(node, value)], end_label)."""
    W, H = 640, height
    ml, mr, mt, mb = 62, 132, 26, 44
    pw, ph = W - ml - mr, H - mt - mb
    xs = NODES
    xl = lambda n: ml + 10 + NODES.index(n) * (pw - 20) / (len(NODES) - 1)
    vals = [v for s in series for _, v in s["pts"] if v > 0]
    lo = ymin if ymin is not None else min(vals)
    hi = ymax if ymax is not None else max(vals)
    if logy:
        lo = 10 ** (math.floor(math.log10(min(vals) if ymin is None else ymin) * 2) / 2)
        hi = 10 ** (math.ceil(math.log10(max(vals) if ymax is None else ymax) * 2) / 2)
        yv = lambda v: mt + ph - (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo)) * ph
        ticks = log_ticks(lo, hi)
        if len(ticks) > 9:
            ticks = [t for t in ticks if str(t)[0] == "1"]
    else:
        yv = lambda v: mt + ph - (v - lo) / (hi - lo) * ph
        step = (hi - lo) / 5
        mag = 10 ** math.floor(math.log10(step))
        step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= step))
        ticks, v = [], math.ceil(lo / step) * step
        while v <= hi + 1e-9:
            ticks.append(round(v, 10)); v += step
    o = [f'<svg viewBox="0 0 {W} {H}" class="chart" id="{cid}" role="img" aria-label="{html.escape(title)}">']
    xb = (xl(22) + xl(20)) / 2
    o.append(f'<rect x="{xb:.1f}" y="{mt}" width="{ml+pw-xb:.1f}" height="{ph}" class="finband"/>'
             f'<text x="{xb+6:.1f}" y="{mt-9}" class="bandlab">FinFET (BSIM-CMG) →</text>'
             f'<text x="{xb-6:.1f}" y="{mt-9}" class="bandlab" text-anchor="end">← planar bulk</text>')
    for t in ticks:
        y = yv(t)
        o.append(f'<line x1="{ml}" x2="{ml+pw}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                 f'<text x="{ml-8}" y="{y+4:.1f}" class="tick" text-anchor="end">{t:,g}</text>')
    for n in xs:
        x = xl(n)
        o.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{mt+ph}" y2="{mt+ph+5}" class="axis"/>'
                 f'<text x="{x:.1f}" y="{mt+ph+20}" class="tick" text-anchor="middle">{n}</text>')
    o.append(f'<line x1="{ml}" x2="{ml+pw}" y1="{mt+ph}" y2="{mt+ph}" class="axis"/>')
    o.append(f'<text x="{ml+pw/2}" y="{H-6}" class="axlab" text-anchor="middle">기술 노드 [nm]</text>')
    o.append(f'<text transform="translate(14 {mt+ph/2}) rotate(-90)" class="axlab" text-anchor="middle">'
             f'{html.escape(ylabel)}</text>')
    used = []
    for s in series:
        pts = [(xl(n), yv(v), n, v) for n, v in s["pts"] if v > 0]
        d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y, _, _) in enumerate(pts))
        o.append(f'<path d="{d}" class="ln {s["cls"]}{" dash" if s.get("dash") else ""}"/>')
        for x, y, n, v in pts:
            if s["marker"] == "s":
                o.append(f'<rect x="{x-4.5:.1f}" y="{y-4.5:.1f}" width="9" height="9" rx="1.5" class="mk {s["cls"]}"/>')
            elif s["marker"] == "d":
                o.append(f'<path d="M{x:.1f},{y-5.5:.1f} L{x+5.5:.1f},{y:.1f} L{x:.1f},{y+5.5:.1f} L{x-5.5:.1f},{y:.1f}Z" class="mk {s["cls"]}"/>')
            elif s["marker"] == "t":
                o.append(f'<path d="M{x:.1f},{y-5.5:.1f} L{x+5.5:.1f},{y+4.5:.1f} L{x-5.5:.1f},{y+4.5:.1f}Z" class="mk {s["cls"]}"/>')
            else:
                o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" class="mk {s["cls"]}"/>')
            tip = f'{s["name"]} · {n} nm: {fmt(v, 4)} {unit}'
            o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" class="hit" data-tip="{html.escape(tip)}"/>')
        # end label at 22nm, nudged to avoid collisions
        x, y, _, _ = pts[-1]
        while any(abs(y - u) < 13 for u in used):
            y += 13
        used.append(y)
        o.append(f'<text x="{x+12:.1f}" y="{y+4:.1f}" class="endlab">{html.escape(s["short"])}</text>')
    o.append("</svg>")
    leg = "".join(f'<span class="lg"><svg width="26" height="12" aria-hidden="true"><line x1="1" y1="6" x2="25" y2="6" '
                  f'class="ln {s["cls"]}{" dash" if s.get("dash") else ""}"/></svg>{html.escape(s["name"])}</span>' for s in series)
    return (f'<figure class="chartfig"><figcaption class="ctitle">{html.escape(title)}</figcaption>'
            f'<div class="legend">{leg}</div><div class="svgwrap">{"".join(o)}</div></figure>')


def cfg_series(key, corner_fn=MAIN, cfgs=("intrinsic", "layout", "wire10", "wire100"), transform=None):
    marks = {"intrinsic": "c", "layout": "s", "wire10": "d", "wire100": "t"}
    short = {"intrinsic": "소자만", "layout": "레이아웃", "wire10": "+10µm", "wire100": "+100µm"}
    out = []
    for i, c in enumerate(cfgs):
        pts = []
        for t in TECHS:
            v = G(t.node, corner_fn(t), c)[key]
            if transform:
                v = transform(t, corner_fn(t), v)
            pts.append((t.node, v))
        out.append(dict(name=CFG_LABEL[c], short=short[c], cls=f"o{['intrinsic','layout','wire10','wire100'].index(c)+1}",
                        marker=marks[c], pts=pts))
    return out


def hp_lp_series(key, cfg="layout", transform=None):
    a, b = [], []
    for t in TECHS:
        v = G(t.node, MAIN(t), cfg)[key]
        a.append((t.node, transform(t, MAIN(t), v) if transform else v))
        c = LPC(t)
        if c:
            v = G(t.node, c, cfg)[key]
            b.append((t.node, transform(t, c, v) if transform else v))
    return [dict(name="bulk / HP", short="bulk/HP", cls="c1", marker="c", pts=a),
            dict(name="LP / LSTP (저전력)", short="LP/LSTP", cls="c2", marker="s", pts=b)]


# ------------------------------------------------------------------ tables
def table(head, body, cls=""):
    th = "".join(f"<th>{h}</th>" for h in head)
    tr = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in body)
    return f'<div class="tablewrap"><table class="{cls}"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'


def tech_table():
    body = []
    for t in TECHS:
        ro = build_ro(t)
        um = t.lam * 1e6
        m = t.metal()
        cs = " / ".join(f"{k.upper()} {v[1]:.2f}" for k, v in t.corners.items()).replace("BULK ", "")
        if t.finfet:
            cs = f"HP/LSTP {t.corners['hp'][1]:.2f}"
            mod = f"BSIM-CMG (OSDI), {t.nfin[0]}/{t.nfin[1]} fin"
        else:
            mod = "BSIM3 (49)" if t.node == 180 else "BSIM4 (54)"
        body.append([NLAB(t), mod, cs, f"{t.L*1e9:.0f}", f"{t.lam*1e9:.1f}",
                     f"{INV_W*um:.2f} × {CELL_H*um:.2f}", f"{ro.area_um2():.2f}",
                     f"{3*t.lam*1e9:.0f} / {t.ar:.1f}", f"{t.k:.2f}", f"{t.rho*1e8:.1f}",
                     f"{m.r()*1e-6:.2f}", f"{m.c_total()*1e9:.3f}", f"{t.r_contact:.0f}"])
    return table(["노드 [nm]", "모델", "VDD [V]", "L [nm]", "λ [nm]", "INV 셀 [µm]", "RO 면적 [µm²]",
                  "금속 W [nm] / AR", "k", "ρ<sub>eff</sub> [µΩ·cm]", "M1 r [Ω/µm]", "M1 c [fF/µm]",
                  "콘택 R [Ω]"], body, "num")


def extract_table():
    body = []
    for t in TECHS:
        ex = extract(build_ro(t))
        a, b = ex["n5"], ex["n20"]
        body.append([NLAB(t), f"{sum(a['len_um'].values()):.2f}", f"{a['R']:.0f}", f"{a['C']*1e15:.3f}",
                     f"{b['len_um'].get('metal2', 0):.1f}", f"{b['R']:.0f}", f"{b['C']*1e15:.2f}"])
    return table(["노드 [nm]", "단간 net 배선 길이 [µm]", "R [Ω]", "C [fF]",
                  "피드백 M2 길이 [µm]", "피드백 R [Ω]", "피드백 C [fF]"], body, "num")


def result_table():
    body = []
    for t in TECHS:
        for c in t.corners:
            a, b, w1, w2 = (G(t.node, c, k) for k in ("intrinsic", "layout", "wire10", "wire100"))
            body.append([NLAB(t), c.upper() if c != "bulk" else "bulk", f"{b['vdd']:.2f}",
                         f"{a['freq_GHz']:.3f}", f"{b['freq_GHz']:.3f}",
                         f"{100*(1-b['freq_GHz']/a['freq_GHz']):.1f}", f"{b['tstage_ps']:.2f}",
                         f"{w1['freq_GHz']:.3f}", f"{w2['freq_GHz']:.4f}",
                         f"{b['P_total_uW']:.1f}", f"{b['E_cycle_fJ']:.2f}", f"{b['Ceff_stage_fF']:.2f}",
                         f"{b['P_leak_uW']*1e3:.2f}", f"{b['P_leak_uW']*1e3/b['area_um2']:.2f}"])
    return table(["노드", "코너", "VDD", "f 소자만 [GHz]", "f 레이아웃 [GHz]", "배선 손실 [%]", "단 지연 [ps]",
                  "f +10µm", "f +100µm", "P [µW]", "E/cycle [fJ]", "C<sub>eff</sub>/단 [fF]",
                  "누설 [nW]", "누설 밀도 [nW/µm²]"], body, "num")


def reff_table():
    body = []
    for t in TECHS:
        c = MAIN(t)
        a, b = G(t.node, c, "layout"), G(t.node, c, "wire100")
        m = t.metal("M2")
        rw, cw = m.r() * 100e-6, m.c_total() * 100e-6
        el = 0.38 * rw * cw
        reff = ((b["tstage_ps"] - a["tstage_ps"]) * 1e-12 - el) / (0.69 * cw)
        body.append([NLAB(t), f"{reff/1e3:.1f}", f"{rw:.0f}", f"{cw*1e15:.1f}",
                     f"{0.69*reff*cw*1e12:.0f}", f"{el*1e12:.1f}", f"{b['tstage_ps']:.0f}"])
    return table(["노드 [nm]", "최소 인버터 R<sub>eff</sub> [kΩ]", "100 µm 배선 R [Ω]", "C [fF]",
                  "0.69·R<sub>eff</sub>·C<sub>w</sub> [ps]", "0.38·R<sub>w</sub>·C<sub>w</sub> [ps]", "단 지연 [ps]"],
                 body, "num")


# ------------------------------------------------------------------ page
def build():
    k = lambda n, c, key, cfg="layout": G(n, c, cfg)[key]
    f180, f7 = k(180, "bulk", "freq_GHz", "intrinsic"), k(7, "hp", "freq_GHz", "intrinsic")
    fl180, fl7 = k(180, "bulk", "freq_GHz"), k(7, "hp", "freq_GHz")
    e180, e7 = k(180, "bulk", "E_cycle_fJ"), k(7, "hp", "E_cycle_fJ")
    a180, a7 = build_ro(TECHS[0]).area_um2(), build_ro(TECHS[-1]).area_um2()

    charts = [
        line_chart("c-freq", "발진 주파수 (bulk/HP 코너, 공칭 VDD)", cfg_series("freq_GHz"), "주파수 [GHz]",
                   unit="GHz", height=320),
        line_chart("c-loss", "배선 parasitic 에 의한 주파수 감소 (소자만 대비)",
                   cfg_series("freq_GHz", cfgs=("layout", "wire10", "wire100"),
                              transform=lambda t, c, v: 100 * (1 - v / G(t.node, c, "intrinsic")["freq_GHz"])),
                   "주파수 감소 [%]", logy=False, ymin=0, ymax=100, unit="%", height=320),
        line_chart("c-energy", "사이클당 에너지 (레이아웃 추출)", hp_lp_series("E_cycle_fJ"), "E / cycle [fJ]",
                   unit="fJ"),
        line_chart("c-power", "총 소비전력 (레이아웃 추출, 공칭 VDD)", hp_lp_series("P_total_uW"), "전력 [µW]",
                   unit="µW"),
        line_chart("c-leak", "누설전력 밀도 (EN=0, 27 °C)",
                   hp_lp_series("P_leak_uW", transform=lambda t, c, v: v * 1e3 / build_ro(t).area_um2()),
                   "누설 밀도 [nW/µm²]", unit="nW/µm²"),
        line_chart("c-flp", "HP vs LP/LSTP 주파수 (레이아웃 추출)", hp_lp_series("freq_GHz"), "주파수 [GHz]",
                   unit="GHz"),
    ]

    body = f"""
<header class="top">
  <div class="wrap">
    <p class="eyebrow">PTM 180nm – 7nm · planar bulk + FinFET · ngspice-45.2 (OSDI) · 21-stage ring oscillator</p>
    <h1>PTM 링 오실레이터 노드 비교</h1>
    <p class="lede">같은 셀 토폴로지로 그린 레이아웃에서 배선 parasitic 을 추출해 12개 노드(planar bulk 7개, FinFET 5개),
    20개 소자 코너에서 주파수·전력·에너지·누설을 비교했습니다. 소자만 있는 경우, 레이아웃 추출, 단마다 10 µm / 100 µm
    배선을 더한 경우를 함께 시뮬레이션해 배선이 스케일링에서 차지하는 비중을 분리했습니다.</p>
    <dl class="kpis">
      <div><dt>소자 주파수 180nm → 7nm</dt><dd>{f180:.2f} → {f7:.1f} <small>GHz</small></dd></div>
      <div><dt>레이아웃 포함 주파수</dt><dd>{fl180:.2f} → {fl7:.1f} <small>GHz</small></dd></div>
      <div><dt>사이클당 에너지</dt><dd>{e180:.0f} → {e7:.2f} <small>fJ</small></dd></div>
      <div><dt>RO 면적</dt><dd>{a180:.0f} → {a7:.2f} <small>µm²</small></dd></div>
      <div><dt>레이아웃 배선 주파수 손실</dt><dd>{100*(1-fl180/f180):.0f} → {100*(1-fl7/f7):.0f} <small>%</small></dd></div>
    </dl>
  </div>
</header>

<main class="wrap">
<section>
<h2>핵심 결과</h2>
<ol class="findings">
<li><b>planar 의 한계와 FinFET 의 반등.</b> 소자만의 주파수는 180nm 0.51 GHz → 22nm bulk HP 4.04 GHz 로 오르다 45nm 이후
둔화되지만(45→22nm +18%), FinFET 으로 넘어가며 20nm 11.0 GHz → 7nm 40.6 GHz 로 다시 크게 뛰어오릅니다. 핀 하나가
최소 bulk 트랜지스터보다 2배 넘는 전류(약 115–140 µA/fin)를 내면서 소자 커패시턴스는 더 작기 때문입니다.</li>
<li><b>배선 비중은 노드마다 커지고, FinFET 에서 급증.</b> 최소 레이아웃의 짧은 배선만으로도 주파수 손실이 180nm 13% →
22nm 22% → 7nm HP 43% (LSTP 49%)로 늘어납니다. 소자가 빨라지고 작아질수록 같은 셀 안의 배선이 상대적으로 무거워집니다.</li>
<li><b>고정 길이 배선에서는 이득이 사라짐.</b> 단마다 100 µm 배선을 붙이면 가장 빠른 노드는 130nm bulk(0.241 GHz)이고,
14nm FinFET(0.230)이 그와 비슷하며 7nm 는 0.166 GHz 로 다시 느려집니다. 22nm bulk 는 0.100 GHz 로 최저입니다.
배선이 지배하는 회로에서는 소자 세대가 바뀌어도 속도가 거의 오르지 않습니다.</li>
<li><b>원인: 구동 저항과 배선 R.</b> 배선 C/µm 은 노드와 무관하게 0.15–0.20 fF/µm 입니다. 최소 인버터의 등가 저항은
planar 에서 6.1 kΩ(130nm) → 19.7 kΩ(22nm)로 커졌다가 FinFET 에서 7–9.5 kΩ 로 회복되지만, 금속 r 이 0.19 → 100 Ω/µm 로
500배 늘어 7nm 에서는 100 µm 배선 자체의 RC(55 ps)가 단 지연 143 ps 의 약 40%를 차지합니다.</li>
<li><b>에너지는 CV² 로 계속 감소, 누설 밀도는 높게 유지.</b> 사이클당 에너지는 702 fJ → 1.9 fJ (약 370배) 줄어듭니다.
누설 밀도는 180nm 0.16 → 22nm bulk 73 nW/µm² 로 늘고, FinFET 에서도 48–78 nW/µm² 수준입니다. 저누설 코너(LP/LSTP)는
누설이 110–290배 작은 대신 planar LP 는 3.4–4.4배, FinFET LSTP 는 1.4–2.1배 느립니다.</li>
</ol>
</section>

<section>
<h2>실험 구성</h2>
<div class="two">
<div class="prose">
<p>회로는 enable 용 NAND2 1개와 인버터 20개로 된 21단 링입니다. planar 노드는 drawn L = 노드, Wn = 2L, Wp = 4L 이고
PTM 카드의 <code>xl</code> 이 drawn 과 printed 게이트 길이 차이를 보정합니다. FinFET 노드는 PTM-MG 카드의 L 과 핀
형상을 쓰고, 최소 크기로 NMOS·PMOS 각 1 fin 입니다(PMOS 핀 전류가 NMOS 의 0.88–0.93배라 1:1 이 균형).</p>
<p>네 가지 구성을 노드·코너마다 시뮬레이션했습니다.</p>
<ul>
<li><b>소자만</b>: 소자 모델의 parasitic 만 반영(planar 는 레이아웃의 AD/AS/PD/PS 포함), 배선 없음</li>
<li><b>레이아웃 추출</b>: 모든 신호 net 의 M1/M2/게이트 배선과 콘택·비아를 RC π 래더로 추가</li>
<li><b>+10 µm / +100 µm</b>: 레이아웃 추출에 단마다 중간층 배선(분포 RC)을 더함 — 셀 사이를 실제로 라우팅할 때의 부하</li>
</ul>
<p>주파수는 v(n1) 의 VDD/2 상승 교차 간격, 전력은 정수 주기 동안 I(VDD) 적분, 누설은 EN = 0 정지 상태의 DC 전류입니다.</p>
</div>
<div class="prose">
<p><b>FinFET 모델.</b> PTM-MG 는 BSIM-CMG(HSPICE level 72, 105.03) 카드입니다. 공개 BSIM-CMG 111.0.0 Verilog-A 를
OpenVAF 로 OSDI 라이브러리로 컴파일하고, OSDI 를 켠 ngspice-45.2 에서 불러왔습니다. 111.0.0 에 없는 14개 파라미터
(lmin/lmax 등 binning 한계, version, capmod·coremod 등 대부분 0 인 플래그, vasat·vasatcv·ldg·nseg)는 제외했습니다.
planar 노드 결과는 ngspice-42 와 45.2 에서 동일함을 확인했습니다.</p>
<p><b>배선 모델.</b> 금속 폭·간격은 레이아웃 규칙 그대로 3λ, 두께 = AR × 폭, ILD 높이 = 두께입니다. C 는 PTM 배선 모델의
closed-form 식(양옆 이웃 + 접지면, Miller 계수 1), R 은 크기 효과와 배리어를 포함한 유효 비저항 ρ<sub>eff</sub> 로
계산합니다. AR, k, ρ<sub>eff</sub>, FinFET 의 M1 피치는 업계·ITRS 추세 수준의 가정치입니다. 게이트는 8 Ω/□,
콘택 저항은 10 Ω × (180/노드)로 둡니다.</p>
</div>
</div>
{tech_table()}
</section>

<section>
<h2>레이아웃</h2>
<p class="prose">레이아웃은 SCMOS 계열의 단순화된 λ 규칙으로 생성했습니다. planar 노드는 λ = L/2, FinFET 노드는 실제 셀 크기에
맞도록 λ = M1 피치/6 입니다(7nm 인버터 107 × 253 nm, 실제 2 CPP × 6-track 셀과 비슷). 모든 노드가 λ 단위로 같은 도면이라
배선 길이는 λ 에 비례합니다. 도형마다 net 이름을 달아 두고 그로부터 R·C 를 계산합니다. GDS 파일은
<code>ringosc/results_nodes/layout/</code> 에 있습니다.</p>
{legend_layers()}
{cells_figure()}
{ro_figure(45)}
<h3>planar bulk: 같은 축척</h3>
{scaling_figure()}
<h3>FinFET</h3>
{finfet_figures()}
<h3>추출된 parasitic</h3>
<p class="prose">단간 net 은 구동 셀의 출력 M1 스트랩, 셀 사이 M1 링크, 다음 셀의 입력 패드와 field 게이트로 이루어집니다.
피드백 net 은 행 전체를 가로지르는 M2 트랙이라 C 가 단간 net 의 약 8배입니다. 같은 λ 도면이라 C 는 λ 에 비례해 줄지만,
R 은 단면적이 λ² 로 줄고 ρ<sub>eff</sub> 가 커져 오히려 증가합니다(7nm 단간 net 475 Ω, 피드백 1.03 kΩ).</p>
{extract_table()}
</section>

<section>
<h2>결과</h2>
<p class="prose">음영 구간은 FinFET 노드입니다. x 축은 노드 순서(등간격)입니다.</p>
<div class="grid2">{charts[0]}{charts[1]}</div>
<div class="grid2">{charts[2]}{charts[3]}</div>
<div class="grid2">{charts[4]}{charts[5]}</div>
<h3>전체 결과표</h3>
{result_table()}
</section>

<section>
<h2>분석</h2>
<h3>고정 길이 배선: 무엇이 지연을 정하나</h3>
<p class="prose">+100 µm 구성의 단 지연에서 레이아웃 구성의 단 지연과 배선 자체의 Elmore 항(0.38·R<sub>w</sub>·C<sub>w</sub>)을 빼고
0.69·C<sub>w</sub> 로 나누면 최소 인버터의 등가 구동 저항이 나옵니다. planar 에서는 R<sub>eff</sub> ≈ VDD / (Ion/µm × W)
에서 Ion/µm 이 포화되고 W 가 노드에 비례해 줄어 R<sub>eff</sub> 가 계속 커집니다. FinFET 에서는 핀 하나의 유효 폭(2·H<sub>fin</sub> +
T<sub>fin</sub> ≈ 43–71 nm)과 전류가 커서 R<sub>eff</sub> 가 7–9.5 kΩ 로 내려오지만, 이번에는 배선 R 이 커집니다. 7nm 에서
0.38·R<sub>w</sub>·C<sub>w</sub> 가 55 ps 로 0.69·R<sub>eff</sub>·C<sub>w</sub>(87 ps)에 근접합니다. 긴 배선에 구동기 크기 키우기,
리피터, 상위 금속층(두꺼운 배선) 사용이 필수인 이유입니다.</p>
{reff_table()}
<h3>짧은 배선의 비중</h3>
<p class="prose">최소 레이아웃에서도 배선 손실이 13% → 43%로 커지는 것은, 소자 커패시턴스는 노드에 비례해 줄어드는 반면
배선 C/µm 은 거의 줄지 않아 같은 λ 길이의 배선이 상대적으로 무거워지기 때문입니다. 단당 C<sub>eff</sub> 중 배선 몫은
180nm 13% → 22nm 22% → 7nm 40% 수준입니다. 실제 FinFET 공정에서는 여기에 게이트–콘택(MOL) 결합 커패시턴스가 더해져
비중이 더 큽니다.</p>
<h3>전력과 에너지</h3>
<p class="prose">링 오실레이터는 부하 C 가 커지면 주파수가 같은 비율로 떨어지므로 P = N·C·V²·f 에서 C 가 상쇄됩니다. 그래서
노드 비교는 전력보다 사이클당 에너지(N·C<sub>eff</sub>·V²)가 적절합니다. C<sub>eff</sub>/단은 180nm 10.3 fF → 22nm 0.58 fF →
7nm 0.18 fF, VDD² 는 3.24 → 0.49 로 줄어 에너지가 약 370배 감소합니다. 20nm FinFET 은 VDD 가 22nm bulk(0.8 V)보다 높은
0.9 V 라 사이클당 에너지가 약간 큽니다.</p>
<h3>저누설 코너</h3>
<p class="prose">planar LP 는 Vth 가 높아(약 0.62–0.69 V) VDD 를 올려도 HP 보다 3.4–4.4배 느립니다. FinFET LSTP 는 같은 VDD 에서
1.4–2.1배 느릴 뿐이며 누설은 150–290배 작습니다. 핀 구조의 게이트 장악력 덕분에 저누설 코너의 속도 손해가 planar 보다
훨씬 작습니다. 다만 노드가 작아질수록 HP/LSTP 속도 차가 커집니다(20nm 1.4배 → 7nm 2.1배).</p>
<h3>모델 경계에서의 불연속</h3>
<p class="prose">180nm 카드는 PTM beta 의 BSIM3 모델로 접합 커패시턴스가 130nm 이하 카드보다 7배 커서 180 → 130nm 향상(2.9배)이
과장되어 있습니다. 22nm bulk → 20nm FinFET 의 2.7배 도약도 모델 계열이 바뀌는 지점입니다. PTM-MG 카드에는 MOL
parasitic 이 거의 없어 FinFET 의 절대 주파수(7nm 소자만 40 GHz, 단 지연 1.2 ps)는 낙관적인 상한으로 봐야 합니다.
같은 계열 안의 추세 비교가 더 신뢰할 만합니다.</p>
</section>

<section>
<h2>한계</h2>
<ul class="prose">
<li>PTM-MG 카드는 BSIM-CMG 105.03 기준인데 공개 111.0.0 모델로 시뮬레이션했습니다. 버전 간 기본값과 일부 식이 다르고
111.0.0 에 없는 14개 파라미터를 제외했으므로, PTM 이 HSPICE 로 발표한 값과 조금 다를 수 있습니다.</li>
<li>λ 규칙은 실제 디자인 룰을 단순화한 것이고, 실제 공정은 λ 처럼 균일하게 축소되지 않습니다(게이트·금속·핀 피치가 각각
다르게 스케일). FinFET 은 λ = M1 피치/6 이라는 별도 기준을 씁니다.</li>
<li>배선 AR·k·ρ<sub>eff</sub>, FinFET M1 피치, 콘택 저항은 가정치입니다. 추출은 레이어별 closed-form 모델로 한 근사
PEX 이며, MOL 결합 커패시턴스·상부 접지면·3차원 프린지·인덕턴스는 빠져 있습니다.</li>
<li>공정 편차(Monte Carlo), 온도·전압 스윕은 노드 비교에 포함하지 않았습니다(45nm 단일 노드 스윕은
<code>ringosc/README.md</code> 참고).</li>
<li>planar 누설 DC 해석에서만 BSIM4 <code>rbodymod=0</code> 을 사용합니다(body 저항망으로 인한 비물리적 DC 해 회피).</li>
</ul>
</section>

<section>
<h2>재현</h2>
<pre><code># FinFET 용 도구 (한 번만): OpenVAF-Reloaded, ngspice-45.2 --enable-osdi
openvaf-r pdk/ptm/osdi/bsimcmg/bsimcmg.va -o pdk/ptm/osdi/bsimcmg.osdi
python3 pdk/ptm/tools/convert_ptmmg.py      # PTM-MG → pdk/ptm/ptmmg.lib

cd ringosc
python3 layout.py                  # 레이아웃(GDS, PNG) + 추출표
NGSPICE=/opt/ngspice-osdi/bin/ngspice python3 multinode.py   # 60개 시뮬레이션
python3 report.py                  # 이 리포트(report/index.html)</code></pre>
<p class="prose">모델: <code>pdk/ptm/ptm.lib</code> (n180 … n22lp), <code>pdk/ptm/ptmmg.lib</code> (f20hp … f7lstp).
출처: Predictive Technology Model (mec.umn.edu/ptm), BSIM-CMG 111.0.0 (UC Berkeley, ECL-2.0), OpenVAF-Reloaded.</p>
</section>
</main>
<div id="tip" role="tooltip" hidden></div>
"""
    return PAGE.replace("%%BODY%%", body)


PAGE = r"""<title>PTM 링 오실레이터 노드 비교</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: single reading column (≈1060px) with full-bleed header band; figures and tables break wider inside scroll boxes. */
:root {
  --bg: #f7f8f9; --surface: #ffffff; --ink: #14181d; --ink-2: #4a525c; --ink-3: #737b85;
  --rule: #dfe3e8; --copper: #a4502a; --copper-soft: #f3e3d9; --code: #eef1f4;
  --o1: #86b6ef; --o2: #3987e5; --o3: #1c5cab; --o4: #0d366b; --c1: #2a78d6; --c2: #eb6834;
  --grid: #e6e9ed;
  --l-nwell: #9fd49a; --l-active: #2f8f3a; --l-nplus: #e9c77a; --l-pplus: #d79ac0; --l-poly: #d1302f;
  --l-contact: #15181c; --l-metal1: #2f7fd1; --l-via1: #4b4f55; --l-metal2: #f08a1c; --lay-bg: #ffffff;
  --l-fin: #6b4f1d;
  --font: "IBM Plex Sans KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #121417; --surface: #1a1d21; --ink: #eceef0; --ink-2: #b4bac2; --ink-3: #8d949d;
  --rule: #2c3138; --copper: #e08a5c; --copper-soft: #3a2519; --code: #22262b;
  --o1: #184f95; --o2: #2a78d6; --o3: #6da7ec; --o4: #b7d3f6; --c1: #3987e5; --c2: #d95926;
  --grid: #262b31; --l-contact: #e9ecef; --l-via1: #c5cad0; --lay-bg: #15181b; --l-fin: #d9b26a; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #121417; --surface: #1a1d21; --ink: #eceef0; --ink-2: #b4bac2; --ink-3: #8d949d;
  --rule: #2c3138; --copper: #e08a5c; --copper-soft: #3a2519; --code: #22262b;
  --o1: #184f95; --o2: #2a78d6; --o3: #6da7ec; --o4: #b7d3f6; --c1: #3987e5; --c2: #d95926;
  --grid: #262b31; --l-contact: #e9ecef; --l-via1: #c5cad0; --lay-bg: #15181b; --l-fin: #d9b26a; color-scheme: dark }
body { background: var(--bg); color: var(--ink); font-family: var(--font); font-size: 15.5px; line-height: 1.7; }
.wrap { max-width: 1060px; margin: 0 auto; padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px)); }
.top { background: var(--surface); border-bottom: 1px solid var(--rule); }
.top .wrap { padding-block: 40px 28px; }
.eyebrow { font-family: var(--mono); font-size: 12.5px; color: var(--copper); letter-spacing: .02em; margin: 0 0 6px; }
h1 { font-size: clamp(28px, 4vw, 40px); line-height: 1.2; margin: 0 0 12px; font-weight: 700; text-wrap: balance; }
.lede { max-width: 68ch; color: var(--ink-2); margin: 0 0 24px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 0; }
.kpis div { border-top: 2px solid var(--copper); padding-top: 8px; }
.kpis dt { font-size: 12.5px; color: var(--ink-3); }
.kpis dd { margin: 2px 0 0; font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; }
.kpis small { font-size: 13px; color: var(--ink-3); font-weight: 400; }
main { padding-block: 8px 64px; }
section { padding-top: 36px; }
h2 { font-size: 23px; margin: 0 0 14px; padding-bottom: 6px; border-bottom: 1px solid var(--rule); text-wrap: balance; }
h3 { font-size: 17px; margin: 26px 0 8px; }
.prose, .prose p, .prose li { max-width: 74ch; }
p { margin: 0 0 12px; }
code { font-family: var(--mono); font-size: .88em; background: var(--code); padding: 1px 5px; border-radius: 4px; }
pre { background: var(--code); padding: 14px 16px; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
.findings { padding-left: 1.3em; display: grid; gap: 10px; max-width: 82ch; }
.findings b { color: var(--ink); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; margin-bottom: 18px; }
.two > *, .grid2 > * { min-width: 0; }
@media (max-width: 800px) { .two, .grid2 { grid-template-columns: 1fr; } }
figure { margin: 18px 0; }
figcaption { font-size: 13.5px; color: var(--ink-2); margin-top: 6px; max-width: 90ch; }
.svgwrap { background: var(--surface); border: 1px solid var(--rule); border-radius: 6px; padding: 10px; }
.svgwrap.scroll { overflow-x: auto; }
.svgwrap.scroll svg { min-width: 760px; }
svg { display: block; width: 100%; height: auto; }
.cells { display: grid; grid-template-columns: 1.55fr 1fr; gap: 18px; max-width: 760px; }
.cells > * { min-width: 0; }
.lay-bg { fill: var(--lay-bg); }
.lay-grid { stroke: var(--grid); stroke-width: .6; }
.L-nwell { fill: var(--l-nwell); fill-opacity: .35; } .L-active { fill: var(--l-active); fill-opacity: .7; }
.L-nplus { fill: var(--l-nplus); fill-opacity: .22; } .L-pplus { fill: var(--l-pplus); fill-opacity: .22; }
.L-poly { fill: var(--l-poly); fill-opacity: .82; } .L-contact { fill: var(--l-contact); }
.L-metal1 { fill: var(--l-metal1); fill-opacity: .5; } .L-via1 { fill: var(--l-via1); }
.L-metal2 { fill: var(--l-metal2); fill-opacity: .55; }
.L-fin { fill: var(--l-fin); fill-opacity: .9; }
.chart .finband { fill: var(--copper); fill-opacity: .06; }
.chart .bandlab { font: 11px var(--font); fill: var(--ink-3); }
.lay-lbl { font: 600 10px var(--mono); fill: var(--ink); }
.lay-node { font: 600 15px var(--font); fill: var(--ink); }
.lay-note { font: 12.5px var(--mono); fill: var(--ink-2); }
.lay-scale { stroke: var(--ink); stroke-width: 2; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12.5px; color: var(--ink-2); margin: 6px 0 4px; }
.lg { display: inline-flex; align-items: center; gap: 6px; }
.lg svg { width: auto; display: inline-block; }
.chartfig { margin: 0; }
.ctitle { font-weight: 600; color: var(--ink); font-size: 14.5px; margin: 0; }
.chart .grid { stroke: var(--grid); stroke-width: 1; }
.chart .axis { stroke: var(--ink-3); stroke-width: 1; }
.chart .tick { font: 11px var(--mono); fill: var(--ink-3); font-variant-numeric: tabular-nums; }
.chart .axlab { font: 12px var(--font); fill: var(--ink-2); }
.chart .endlab { font: 11.5px var(--font); fill: var(--ink-2); }
.ln { fill: none; stroke-width: 2; stroke-linejoin: round; } .ln.dash { stroke-dasharray: 5 4; }
.mk { stroke: var(--surface); stroke-width: 2; }
.ln.o1 { stroke: var(--o1); } .mk.o1 { fill: var(--o1); } .ln.o2 { stroke: var(--o2); } .mk.o2 { fill: var(--o2); }
.ln.o3 { stroke: var(--o3); } .mk.o3 { fill: var(--o3); } .ln.o4 { stroke: var(--o4); } .mk.o4 { fill: var(--o4); }
.ln.c1 { stroke: var(--c1); } .mk.c1 { fill: var(--c1); } .ln.c2 { stroke: var(--c2); } .mk.c2 { fill: var(--c2); }
.hit { fill: transparent; cursor: crosshair; }
.hit:hover, .hit:focus { fill: var(--ink); fill-opacity: .08; outline: none; }
#tip { position: fixed; z-index: 20; pointer-events: none; background: var(--ink); color: var(--bg);
  font: 12px var(--mono); padding: 5px 8px; border-radius: 4px; white-space: nowrap; }
.tablewrap { overflow-x: auto; border: 1px solid var(--rule); border-radius: 6px; background: var(--surface); margin: 14px 0; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { padding: 7px 10px; border-bottom: 1px solid var(--rule); white-space: nowrap; }
th { text-align: left; font-weight: 600; color: var(--ink-2); background: var(--copper-soft); font-size: 12.5px; }
table.num td { font-variant-numeric: tabular-nums; font-family: var(--mono); font-size: 12.5px; text-align: right; }
table.num td:first-child, table.num td:nth-child(2) { text-align: left; }
tbody tr:last-child td { border-bottom: 0; }
table.num td:first-child, table.num th:first-child { position: sticky; left: 0; background: var(--surface); }
table.num th:first-child { background: var(--copper-soft); }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
%%BODY%%
<script>
(function () {
  var tip = document.getElementById('tip');
  function show(e) {
    var t = e.target.getAttribute('data-tip'); if (!t) return;
    tip.textContent = t; tip.hidden = false; move(e);
  }
  function move(e) {
    var x = e.clientX, y = e.clientY;
    if (e.type === 'focus') { var r = e.target.getBoundingClientRect(); x = r.left + r.width / 2; y = r.top; }
    var w = tip.offsetWidth;
    tip.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, x - w / 2)) + 'px';
    tip.style.top = (y - 34) + 'px';
  }
  function hide() { tip.hidden = true; }
  document.querySelectorAll('.hit').forEach(function (el) {
    el.setAttribute('tabindex', '0');
    el.addEventListener('mouseenter', show); el.addEventListener('mousemove', move);
    el.addEventListener('mouseleave', hide); el.addEventListener('focus', show); el.addEventListener('blur', hide);
  });
})();
</script>
"""

if __name__ == "__main__":
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    page = build()
    open(OUT, "w").write(page)
    print(f"wrote {OUT} ({len(page)/1024:.0f} KB)")
