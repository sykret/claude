* PTM45 HP - CMOS inverter VTC and transient delay
.lib "../ptm45.lib" hp
.param vdd=1.0
VDD vdd 0 {vdd}
Vin in  0 pulse(0 {vdd} 100p 20p 20p 480p 1n)
Mp  out in vdd vdd pch W=180n L=45n
Mn  out in 0   0   nch W=90n  L=45n
CL  out 0 1f
.control
dc Vin 0 1.0 0.005
meas dc VM when v(out)=v(in)
tran 1p 2n
meas tran tphl trig v(in) val=0.5 rise=1 targ v(out) val=0.5 fall=1
meas tran tplh trig v(in) val=0.5 fall=1 targ v(out) val=0.5 rise=1
wrdata inv_tran.txt v(in) v(out)
.endc
.end
