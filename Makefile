.PHONY: smolcode

smolcode:
	@PYTHONPATH=$(PWD) uv run app/main.py
