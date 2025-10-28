.PHONY: install install-dev format lint fix test run

install:
python -m pip install --upgrade pip
pip install -e .

install-dev: install
pip install -e .[dev]

format:
black app tests

lint:
ruff check app tests

fix:
ruff check --fix app tests
black app tests

run:
uvicorn app.main:app --reload

pytest-args ?=

test:
pytest $(pytest-args)
