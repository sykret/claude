AHKAB_VER := 0.18
BUILD := build

test:
	python rctest.py rc.sp
test2:
	python rctest.py rc2.sp
default:
	echo "default"

# Install ahkab patched for Python 3.12+ / NumPy 2 / current SciPy.
setup:
	rm -rf $(BUILD) && mkdir -p $(BUILD)
	pip download --no-deps --no-binary :all: ahkab==$(AHKAB_VER) -d $(BUILD)
	tar xzf $(BUILD)/ahkab-$(AHKAB_VER).tar.gz -C $(BUILD)
	cd $(BUILD)/ahkab-$(AHKAB_VER) && patch -p1 < ../../patches/ahkab-$(AHKAB_VER)-py313.patch
	pip install --use-pep517 ./$(BUILD)/ahkab-$(AHKAB_VER)

.PHONY: test test2 default setup
