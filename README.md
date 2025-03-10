# kappybara

## Installation:
TODO: If/when this is shipped as a pypi package.

## Local development:
TODO: Instructions for `pip` for people who don't want to use uv. We can always just export a `requirements.txt` using uv which can be consumed directly by pip.

With `uv` (recommended):

Install [`uv`](https://docs.astral.sh/uv/getting-started/installation/), then:
```
uv sync --dev
```

This will locally install the dependencies listed in `pyproject.toml`. To access dependencies, run your commands through `uv` like:
```
uv run python
```
Or, if you want to run commands normally, create a virtual environment:
```
uv venv # Do this once
source .venv/bin/activate # Do this every new shell
```
and run commands as usual. (`deactivate` exits the venv.)

Adding a Python package dependency (this automatically updates pyproject.toml):
```
uv add [package-name]
```

Adding a package as a dev dependency:
```
uv add --dev [package-name]
```

## Running code formatter
```
black .
```
or:
```
uv run black .
```

## Running tests locally
First, add this project's root directory to PYTHONPATH:
```
export PYTHONPATH="$PYTHONPATH:$(git rev-parse --show-toplevel)
```

Then run tests using pytest:
```
pytest
```
or:
```
uv run pytest
```

## Running performance profiles locally
`cd` into the `tests/cpu-profiles` directory, then run the bash script:
```
cd tests/cpu-profiles
./run_profiler.sh
```
This outputs a CPU profile for each python script in `tests/cpu-profiles`, which can be found in `tests/cpu-profiles/results`.
