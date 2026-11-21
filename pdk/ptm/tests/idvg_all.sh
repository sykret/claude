#!/bin/bash
# Ion/Ioff per um for every PTM section (W=2L for NMOS, W=4L for PMOS)
LIB="$(cd "$(dirname "$0")/.." && pwd)/ptm.lib"
printf "%-6s %5s %5s %10s %10s %10s %10s\n" sec L Vdd "Ion_n[uA/um]" "Ioff_n[nA/um]" "Ion_p[uA/um]" "Ioff_p[nA/um]"
for e in n180:180:1.8 n130:130:1.3 n90:90:1.2 n65:65:1.1 n45hp:45:1.0 n45lp:45:1.1 n32hp:32:0.9 n32lp:32:1.0 n22hp:22:0.8 n22lp:22:0.95; do
  IFS=: read sec L V <<< "$e"
  cat > /tmp/idvg_$sec.sp <<SP
* idvg
.lib "$LIB" $sec
Vd d 0 $V
Vg g 0 0
Mn d g 0 0 nch W=$((2*L))n L=${L}n
Vdp dp 0 -$V
Vgp gp 0 0
Mp dp gp 0 0 pch W=$((4*L))n L=${L}n
.control
op
let ioffn=-i(Vd)
let ioffp=i(Vdp)
echo OFF \$&ioffn \$&ioffp
alter Vg dc=$V
alter Vgp dc=-$V
op
let ionn=-i(Vd)
let ionp=i(Vdp)
echo ON \$&ionn \$&ionp
.endc
.end
SP
  o=$(ngspice -b /tmp/idvg_$sec.sp 2>&1)
  r="X $(echo "$o" | grep '^ON' | cut -d' ' -f2) $(echo "$o" | grep '^OFF' | cut -d' ' -f2) $(echo "$o" | grep '^ON' | cut -d' ' -f3) $(echo "$o" | grep '^OFF' | cut -d' ' -f3)"
  python3 -c "
import sys
_,a,b,c,d=sys.argv[1].split(); L=$L*1e-3
print('%-6s %5d %5.2f %10.0f %10.2f %10.0f %10.2f'%('$sec',$L,$V,float(a)/(2*L)*1e6,float(b)/(2*L)*1e9,abs(float(c))/(4*L)*1e6,abs(float(d))/(4*L)*1e9))" "$r"
done
