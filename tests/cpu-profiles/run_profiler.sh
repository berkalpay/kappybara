#!/usr/bin/env sh

# Get the basename of the current directory
current_dir=$(basename "$PWD")
required_dir="cpu-profiles"

# Only run if in the tests/cpu-profiles directory
if [[ "$current_dir" != "cpu-profiles" ]]; then
    echo "Error: run this in tests/'$required_dir'."
    exit 1  # Exit with a non-zero status to indicate failure
fi

mkdir -p results

# Loop through all profile_*.py files in the current directory
for script_name in *.py; do
    # Extract the base name (without the .py extension)
    base_name="${script_name%.py}"

    # Create the corresponding output file
    output_file="results/${base_name}.svg"

    if command -v "py-spy" >/dev/null 2>&1; then
        py-spy record -o ${output_file} -- python3 ${script_name}
    else
        # In case we're not in the venv
        uv run py-spy record -o ${output_file} -- python3 ${script_name}
    fi
done
