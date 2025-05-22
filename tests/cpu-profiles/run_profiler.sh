#!/usr/bin/env bash

cd "$(dirname "$0")"
mkdir -p results

# Loop through all profile_*.py files in the current directory
for script_name in *.py; do
    base_name="${script_name%.py}"  # Extract the base name
    output_file="results/${base_name}.svg"

    if command -v "py-spy" >/dev/null 2>&1; then
        py-spy record -o ${output_file} -- python3 ${script_name}
    else
        # In case we're not in the venv
        uv run py-spy record -o ${output_file} -- python3 ${script_name}
    fi
done
