# Contributing

## Getting Started

1. Fork the repository on GitHub
2. Clone the forked repository to your local machine
3. Make your changes and add tests
4. Run the tests
5. Run the pre-commit hooks (or install them)
6. Commit your changes
7. Push your changes to your fork
8. Open a pull request

## Running the pre-commit hooks

The pre-commit hooks are managed by [pre-commit](https://pre-commit.com/).
To install them, run:

To run the hooks on all files, install pre-commit and run:

```bash
pre-commit run --all
```

Or to install the hooks so they run automatically on every commit, run:

```bash
pre-commit install
```

## Building the documentation

To build the documentation via `tox`, install it and run:

```bash
tox -e docs-sphinx-latest
```

## Running the tests

The tests are managed by [pytest](https://docs.pytest.org/en/latest/).

They can be run either via creating a virtual environment and running `pytest` in it,
or using [tox](https://tox.wiki) to automatically create the virtual environment and run the tests.

To run the tests via `tox`, install it and run:

```bash
tox
```

or run `tox -av` to see all available environments, and run a specific one via:

```bash
tox -e envname
```

To run manually in an virtual environment, run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[testing]"
pytest
```
