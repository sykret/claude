import pdb
from ahkab import netlist_parser, circuit, ac
import ahkab
import numpy as np
import os, sys


"""
bpf = ahkab.Circuit('RLC bandpass')

bpf.add_inductor('L1', 'in', 'n1', 1e-6)
bpf.add_capacitor('C1', 'n1', 'out', 2.2e-12)
bpf.add_resistor('R1', 'out', bpf.gnd, 13)
# we also give V1 an AC value since we wish to run an AC simulation
# in the following
bpf.add_vsource('V1', 'in', bpf.gnd, dc_value=1, ac_value=1)
"""

fspice = sys.argv[1]
parsed = netlist_parser.parse_circuit(fspice)
cir = parsed[0]
cir.add_vsource('V1', 'n1', cir.gnd , dc_value=1, ac_value=1)
out = 'n8'

pza = ahkab.new_pz('V1', (out, cir.gnd), x0=None, shift=1e3)
r = ahkab.run(cir, pza)['pz']



print('Singularities:')
for x, _ in r:
    print("* %s = %+g %+gj Hz" % (x, np.real(r[x]), np.imag(r[x])))
