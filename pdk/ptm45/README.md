# PTM 45nm bulk CMOS models for ngspice

These are the 45nm model cards from the Predictive Technology Model (PTM), BSIM4 (`level=54`).

| Section | File | Vdd | Description |
|---|---|---|---|
| `hp` | `models/45nm_HP.pm` | 1.0 V | High Performance: metal gate, high-k, strained Si |
| `lp` | `models/45nm_LP.pm` | 1.1 V | Low Power |

- `models/*.pm`: original PTM model cards. They are unchanged, and the model names are `nmos`/`pmos`.
- `ptm45.lib`: an ngspice `.lib` wrapper with both corners as sections. To avoid clashing with the built-in names, the models are renamed `nch` and `pch`.

## Usage

```spice
.lib "/path/to/pdk/ptm45/ptm45.lib" hp      $ or lp
M1 out in 0   0   nch W=90n  L=45n
M2 out in vdd vdd pch W=180n L=45n
```

A relative path in `.lib` is resolved from the netlist file's location.

## Tests

```sh
make ptm45        # from the repository root
# or
cd pdk/ptm45/tests && ngspice -b nmos_idvg.sp && ngspice -b inverter.sp
```

Reference results (ngspice-42, HP, W=90n/L=45n, |Vds|=|Vgs|=1.0 V):

| Item | Value |
|---|---|
| NMOS Ion / Ioff | 112 uA / 1.7 nA |
| PMOS Ion / Ioff | 79 uA / 0.42 nA |
| Inverter (Wp/Wn=180n/90n, CL=1fF) VM | 0.49 V |
| tpHL / tpLH | 10.4 ps / 8.9 ps |

## Source and license

- PTM official site: https://mec.umn.edu/ptm (formerly ptm.asu.edu)
- Mirror these files were taken from: https://github.com/SJTU-YONGFU-RESEARCH-GRP/spice_model_collections (`ptm/`)
- Reference: W. Zhao, Y. Cao, "New generation of Predictive Technology Model for sub-45nm early design exploration," IEEE TED, 2006.
