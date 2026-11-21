# PTM models for ngspice: bulk CMOS 180nm–22nm + FinFET 20nm–7nm

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

## FinFET: PTM-MG 20/16/14/10/7nm (`ptmmg.lib`, BSIM-CMG via OSDI)

PTM-MG cards are BSIM-CMG models (HSPICE level 72, version 105.03). ngspice does not have BSIM-CMG built in, so it is loaded as an OSDI module:

1. Compile the open BSIM-CMG 111.0.0 Verilog-A in `osdi/bsimcmg/` (ECL-2.0) with [OpenVAF-Reloaded](https://github.com/OpenVAF/OpenVAF-Reloaded):
   `openvaf-r osdi/bsimcmg/bsimcmg.va -o osdi/bsimcmg.osdi`
2. Use ngspice 45 built with OSDI enabled (`./configure --enable-osdi`). The ngspice-42 Ubuntu package does not support OSDI.
3. `python3 tools/convert_ptmmg.py` converts `models/*fet_*.pm` into `ptmmg.lib`. Parameters missing from BSIM-CMG 111.0.0 are dropped (14 in total, e.g. lmin/lmax, version, capmod, coremod, vasat), and the full list is in the library header.

```spice
.lib "/path/to/pdk/ptm/ptmmg.lib" f7hp        $ f20hp f20lstp ... f7hp f7lstp
N1 out in 0   0   nch L=11n NFIN=1            $ OSDI devices use the N prefix
N2 out in vdd vdd pch L=11n NFIN=1
.control
pre_osdi /path/to/pdk/ptm/osdi/bsimcmg.osdi
.endc
```

| Section | L [nm] | VDD [V] | Ion_n [uA/fin] | Ioff_n [nA/fin] | Ion_p [uA/fin] | Ioff_p [nA/fin] |
|---|---|---|---|---|---|---|
| f20hp / f20lstp | 24 | 0.90 | 127.5 / 77.8 | 4.42 / 0.004 | 112.8 / 71.0 | 4.85 / 0.005 |
| f16hp / f16lstp | 20 | 0.85 | 136.9 / 79.1 | 3.90 / 0.004 | 119.6 / 71.6 | 4.15 / 0.005 |
| f14hp / f14lstp | 18 | 0.80 | 141.6 / 76.5 | 3.32 / 0.003 | 132.0 / 73.0 | 3.57 / 0.004 |
| f10hp / f10lstp | 14 | 0.75 | 131.7 / 65.8 | 3.34 / 0.003 | 122.1 / 61.3 | 3.70 / 0.004 |
| f7hp / f7lstp   | 11 | 0.70 | 116.7 / 51.4 | 2.90 / 0.003 | 103.1 / 47.7 | 3.15 / 0.003 |

(`tests/idvg_finfet.sh`, ngspice-45.2 + OSDI, |Vgs| = |Vds| = VDD)

## Notes
- The 180nm card contains the HSPICE-only parameter `tref`. ngspice ignores it and prints a warning; its value equals `tnom` (27 C), so the results are unaffected.
- The PTM-MG cards target BSIM-CMG 105.03 but are simulated here with the open 111.0.0 model, so results can differ slightly from PTM's published HSPICE values.
- Source: https://mec.umn.edu/ptm (mirror: SJTU-YONGFU-RESEARCH-GRP/spice_model_collections).
