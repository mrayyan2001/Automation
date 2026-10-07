.PHONY: setup run test clean-deps

-include .env
export

setup:
	uv sync

clear:
	clear

run: clear setup test check format
	uv run src/main.py

test:
	uv run pytest

check:
	uv run ruff check --fix

format:
	uv run ruff format

reset:
	uv cache clean
	rm -rf .venv uv.lock
	uv sync --refresh --upgrade