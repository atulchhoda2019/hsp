PY := .venv/bin/python

.PHONY: lint test validate exemplar-check

lint:
	$(PY) -m ruff check hsp tests

test:
	$(PY) -m pytest -q

validate:
	$(PY) -m hsp.cli validate $(FILE)

exemplar-check:
	$(PY) -m hsp.cli validate-dir corpus/exemplars/json_dsl
