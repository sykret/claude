# test
test:
	python rctest.py rc.sp
test2:
	python rctest.py rc2.sp
default:
	echo "default"
ptm45:
	cd pdk/ptm45/tests && ngspice -b nmos_idvg.sp && ngspice -b inverter.sp
