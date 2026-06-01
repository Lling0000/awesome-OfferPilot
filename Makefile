.PHONY: demo serve test doctor lint format

demo:
	offerpilot demo --reset

serve:
	offerpilot serve --host 127.0.0.1 --port 8000

test:
	pytest

doctor:
	offerpilot doctor --strict-publish

lint:
	ruff check .

format:
	ruff format .
