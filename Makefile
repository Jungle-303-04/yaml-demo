.PHONY: test validate

validate:
	python3 scripts/validate_catalog.py

test: validate
	python3 -m unittest discover -s tests -v

