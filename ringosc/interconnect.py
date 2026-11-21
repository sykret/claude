"""45nm interconnect RC per unit length.

Capacitance uses the PTM interconnect closed-form model for a line between two
neighbours over a ground plane (S.-C. Wong et al., IEEE TED 2000, used by the PTM
interconnect calculator). Resistance is rho_eff / (W*T), where rho_eff includes Cu
size effects and the barrier (taken from the ITRS 45nm-node range).
"""
from dataclasses import dataclass

EPS0 = 8.854e-12  # F/m


@dataclass
class Layer:
    name: str
    w: float      # line width   [m]
    s: float      # line spacing [m]
    t: float      # thickness    [m]
    h: float      # ILD height to ground plane [m]
    k: float      # dielectric constant
    rho: float    # effective resistivity [ohm*m]

    def cg(self):
        """Ground capacitance per length [F/m]."""
        w, s, t, h = self.w, self.s, self.t, self.h
        return EPS0 * self.k * (w / h + 2.04 * (s / (s + 0.54 * h)) ** 1.77
                                * (t / (t + 4.53 * h)) ** 0.07)

    def cc(self):
        """Coupling capacitance to ONE neighbour per length [F/m]."""
        w, s, t, h = self.w, self.s, self.t, self.h
        return EPS0 * self.k * (1.14 * t / s * (h / (h + 2.06 * s)) ** 0.09
                                + 0.74 * (w / (w + 1.59 * s)) ** 1.14
                                + 1.16 * (w / (w + 1.87 * s)) ** 0.16
                                * (h / (h + 0.98 * s)) ** 1.18)

    def c_total(self, mcf=1.0):
        """Effective capacitance per length with two neighbours [F/m].
        mcf: Miller coupling factor (0 = neighbours switch with the line, 1 = neighbours quiet,
        2 = neighbours switch in the opposite direction)."""
        return self.cg() + 2.0 * mcf * self.cc()

    def r(self):
        """Resistance per length [ohm/m]."""
        return self.rho / (self.w * self.t)


# 45nm-node values (ITRS 2007 MPU 45nm, low-k k_eff ~2.9)
LAYERS = {
    "M1": Layer("M1 (local)",        65e-9,  65e-9, 130e-9, 130e-9, 2.9, 4.08e-8),
    "Mx": Layer("Mx (intermediate)", 70e-9,  70e-9, 140e-9, 140e-9, 2.9, 3.52e-8),
    "Mg": Layer("Mg (semi-global)", 140e-9, 140e-9, 300e-9, 300e-9, 2.9, 2.60e-8),
}

if __name__ == "__main__":
    print(f"{'layer':20s} {'r[ohm/um]':>10s} {'Cg[fF/um]':>10s} {'Cc[fF/um]':>10s} {'Ctot(MCF=1)':>12s}")
    for L in LAYERS.values():
        print(f"{L.name:20s} {L.r()*1e-6:10.3f} {L.cg()*1e9:10.4f} {L.cc()*1e9:10.4f} {L.c_total()*1e9:12.4f}")
