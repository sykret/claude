#!/bin/bash
# Ion/Ioff per fin for every PTM-MG section (BSIM-CMG via OSDI). Needs ngspice with OSDI.
NG=${NGSPICE:-/opt/ngspice-osdi/bin/ngspice}
P="$(cd "$(dirname "$0")/.." && pwd)"
printf "%-8s %4s %5s %12s %12s %12s %12s\n" sec L Vdd "Ion_n[uA/fin]" "Ioff_n[nA/fin]" "Ion_p[uA/fin]" "Ioff_p[nA/fin]"
for e in f20hp:24:0.9 f20lstp:24:0.9 f16hp:20:0.85 f16lstp:20:0.85 f14hp:18:0.8 f14lstp:18:0.8 f10hp:14:0.75 f10lstp:14:0.75 f7hp:11:0.7 f7lstp:11:0.7; do
  IFS=: read sec L V <<< "$e"
  cat > /tmp/idvg_$sec.sp <<SP
* finfet idvg
.lib "$P/ptmmg.lib" $sec
Vd d 0 $V
Vg g 0 0
N1 d g 0 0 nch L=${L}n NFIN=1
Vdp dp 0 -$V
Vgp gp 0 0
N2 dp gp 0 0 pch L=${L}n NFIN=1
.control
pre_osdi $P/osdi/bsimcmg.osdi
op
echo OFF \$&i(Vd) \$&i(Vdp)
alter Vg dc=$V
alter Vgp dc=-$V
op
echo ON \$&i(Vd) \$&i(Vdp)
.endc
.end
SP
  o=$($NG -b /tmp/idvg_$sec.sp 2>&1)
  on=($(echo "$o" | grep '^ON')); off=($(echo "$o" | grep '^OFF'))
  python3 -c "print('%-8s %4s %5s %12.1f %12.3f %12.1f %12.3f'%('$sec','$L','$V',-float('${on[1]}')*1e6,-float('${off[1]}')*1e9,float('${on[2]}')*1e6,float('${off[2]}')*1e9))"
done
