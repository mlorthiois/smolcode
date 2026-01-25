.PHONY: smolcode

smolcode:
	@PYTHONPATH=$(PWD) uv run app/main.py

smolcode-oauth:
	@PYTHONPATH=$(PWD) SMOLCODE_OAUTH=true uv run app/main.py

smolcode-api:
	@PYTHONPATH=$(PWD) uv run app/main.py

login:
	@PYTHONPATH=$(PWD) uv run app/main.py login

test:
	uv run python -m unittest
