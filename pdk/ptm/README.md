# PTM bulk CMOS models for ngspice (180nm – 22nm)

The Predictive Technology Model (PTM) model cards are combined into one ngspice `.lib` file, `ptm.lib`. The device names are always `nch` / `pch`, and the drawn gate length L equals the node size. The `xl` term in each card corrects drawn L to the printed (physical) length.

| Section | Source file | Model | Nominal VDD |
|---|---|---|---|
| `n180` | 180nm_bulk.pm | BSIM3 (level 49) | 1.8 V |
| `n130` | 130nm_bulk.pm | BSIM4 (level 54) | 1.3 V |
| `n90`  | 90nm_bulk.pm  | BSIM4 | 1.2 V |
| `n65`  | 65nm_bulk.pm  | BSIM4 | 1.1 V |
| `n45hp` / `n45lp` | 45nm_HP/LP.pm | BSIM4, metal gate / high-k | 1.0 / 1.1 V |
| `n32hp` / `n32lp` | 32nm_HP/LP.pm | BSIM4 | 0.9 / 1.0 V |
| `n22hp` / `n22lp` | 22nm_HP/LP.pm | BSIM4 | 0.8 / 0.95 V |

The model files carry no VDD for 180/130/90/65nm, so the PTM nominal values are used for those nodes.

```spice
.lib "/path/to/pdk/ptm/ptm.lib" n65
M1 out in 0 0 nch W=130n L=65n
```

## Check: Ion / Ioff (`tests/idvg_all.sh`, ngspice-42, NMOS W=2L, PMOS W=4L, |Vgs|=|Vds|=VDD)

| sec | Ion_n [uA/um] | Ioff_n [nA/um] | Ion_p [uA/um] | Ioff_p [nA/um] |
|---|---|---|---|---|
| n180 | 738 | 0.95 | 334 | 0.83 |
| n130 | 973 | 28.1 | 457 | 21.5 |
| n90 | 1061 | 44.1 | 495 | 34.5 |
| n65 | 1100 | 62.4 | 518 | 46.7 |
| n45hp | 1245 | 18.8 | 924 | 4.98 |
| n45lp | 478 | 0.04 | 293 | 0.03 |
| n32hp | 1247 | 44.2 | 924 | 18.9 |
| n32lp | 477 | 0.04 | 305 | 0.04 |
| n22hp | 1202 | 94.3 | 904 | 114 |
| n22lp | 420 | 0.04 | 271 | 0.03 |

## Notes
- The 180nm card contains the HSPICE-only parameter `tref`. ngspice ignores it and prints a warning; its value equals `tnom` (27 C), so the results are unaffected.
- **Not included: PTM-MG FinFET 20/16/14/10/7nm.** These models are BSIM-CMG (HSPICE level 72). ngspice has no built-in BSIM-CMG, so they need ngspice built with OSDI support plus `bsimcmg.osdi` compiled with OpenVAF.
- Source: https://mec.umn.edu/ptm (mirror: SJTU-YONGFU-RESEARCH-GRP/spice_model_collections).
