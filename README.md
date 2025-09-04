# kappybara

## Installation
Kappybara will be made available on PyPI.
In the meantime, install using
```
pip install .
```

## Example

We can initialize a system of a simple reversable binding interaction as follows:
```python
system = System.from_kappa(
    mixture={"A(x[.])": 100, "B(x[.])": 100},
    rules=[
        "A(x[.]), B(x[.]) -> A(x[1]), B(x[1]) @ 1",
        "A(x[1]), B(x[1]) -> A(x[.]), B(x[.]) @ 1",
    ],
    observables={"AB": "|A(x[1]), B(x[1])|"},
)
```
or equivalently from a `.ka`-style string:
```python
system = System.from_ka(
    """
    %init: 100 A(x[.])
    %init: 100 B(x[.])

    %obs: 'AB' |A(x[1]), B(x[1])|

    A(x[.]), B(x[.]) <-> A(x[1]), B(x[1]) @ 1, 1
    """
)
```

100 instances of molecules of type `A` and of type `B`, each with an empty binding domain `x` are created, and we track the number of `AB` complexes.

We're going to simulate this system and plot its behavior, marking certain times of interest.
We'll first simulate until time 1:
```python
times = []
while system.time < 1:
    system.update()
times.append(system.time)
```

We'll now manually instantiate 50 new `A` and `B` molecules each, start tracking the number of free `A`, and simulate until there are no more than 10 free `A` in the mixture:
```python
from kappybara.pattern import Pattern

system.mixture.instantiate("A(x[.]), B(x[.])", 50)

system["A"] = "|A(x[.])|"
while system["A"] > 10:
    system.update()
times.append(system.time)
```

The default simulator provides the most features since it's written directly in Python, but models can be offloaded to [KaSim](https://github.com/Kappa-Dev/KappaTools), a compiled Kappa simulator, for faster simulation.
For example:
```python
system.update_via_kasim(time=1)
```

Finally, let's plot the history of the quantities we tracked:
```python
import matplotlib.pyplot as plt

system.monitor.plot()
for time in times:
    plt.axvline(time, color="black", linestyle="dotted")
plt.show()
```

<h1 align="center">
<img width="400" height="300" alt="demo" src="https://github.com/user-attachments/assets/78eb6555-d3a3-4a67-9d60-e457a633f9d6" />
</h1>

Above it can be seen that the system equilibrates relatively early, new `A` is added and the number of complexes increases, and then observables are computed at the end of a period of computation in KaSim.


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



