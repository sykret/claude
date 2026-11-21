* PTM45 HP - NMOS/PMOS Id-Vgs, Vds=|1.0V|, W=90n L=45n
.lib "../ptm45.lib" hp
.param vdd=1.0
Vd  d  0 {vdd}
Vg  g  0 0
Mn  d  g 0 0 nch W=90n L=45n
Vdp dp 0 {-vdd}
Vgp gp 0 0
Mp  dp gp 0 0 pch W=90n L=45n
.control
dc Vg 0 1.0 0.01 
let idn = -i(Vd)
meas dc Ion_n  find idn at=1.0
meas dc Ioff_n find idn at=0
dc Vgp 0 -1.0 -0.01
let idp = i(Vdp)
meas dc Ion_p  find idp at=-1.0
meas dc Ioff_p find idp at=0
wrdata idvg_p.txt idp
.endc
.end
