### Running tests locally
Add this project's root directory to PYTHONPATH:
```
export PYTHONPATH="$PYTHONPATH:$(git rev-parse --show-toplevel)
```

Run tests using pytest:
```
pytest
```

### Running performance profiles locally
`cd` into the `tests/profiles` directory, then run the bashscript

```
cd profiles
./run_profiler.sh
```

