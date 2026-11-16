PY ?= python3
.PHONY: validate test check balance balance-quick
validate:
	$(PY) -I tools/content_validator.py
test:
	$(PY) -m unittest discover -s tests
check: validate test
balance:
	$(PY) tools/balance_sim.py
balance-quick:
	$(PY) tools/balance_sim.py --quick
