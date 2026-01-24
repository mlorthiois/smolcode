.PHONY: smolcode

smolcode:
	@PYTHONPATH=$(PWD) uv run app/main.py

oauth:
	@PYTHONPATH=$(PWD) SMOLCODE_OAUTH=true uv run app/main.py

login:
	@PYTHONPATH=$(PWD) uv run app/main.py login
