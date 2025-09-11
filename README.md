# kappybara

## Installation
Kappybara will be made available on PyPI.
In the meantime, install using
```
pip install .
```


## Development
With `pip` also install:
```
pip install -r requirements.txt
```

<details>
<summary> With uv (optional alternative to pip): </summary>
Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```
uv sync --dev
```

To access `uv` dependencies, run your commands through `uv` like
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
</details>

To run correctness tests, run `pytest`.
Running `./tests/cpu-profiles/run_profiler.sh` will CPU-profile predefined Kappa models and write the results to `tests/cpu-profiles/results`.
We use the Black code formatter, which can be run as `black .`



