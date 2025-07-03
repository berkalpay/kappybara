#!/usr/bin/env bash

cd "$(dirname "$0")"
mkdir -p results

for script_name in profile_*.py; do
    python bench.py ${script_name}
done
