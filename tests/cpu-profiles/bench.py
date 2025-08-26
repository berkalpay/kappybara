import argparse
import time
import memory_profiler
import subprocess
import sys
import json
from pathlib import Path


def profile_python_file(filename):
    """
    Profile the execution of a Python file, measuring runtime and peak memory usage,
    and producing a CPU flamegraph.
    """
    if not Path(filename).exists():
        print(f"Error: File '{filename}' not found", file=sys.stderr)
        sys.exit(1)

    base_name = filename.replace(".py", "")
    mem_profile_name = f"results/{base_name}_memprofile.dat"
    mem_plot_name = f"results/{base_name}_memplot.png"
    flamegraph_name = f"results/{base_name}_flamegraph.svg"
    commit_hash = get_git_short_hash()
    json_name = "results/summary.json"
    title = f"{filename}, commit {commit_hash}"

    print(f"Profiling execution of {filename}...")

    # ======================== Memory ========================
    # Memory profiling requires a separate run since it adds artifacts
    # to the stack trace and also produces some overhead not attributable
    # to the actual program being profiled.
    print("\nMemory profiling:")
    mem_result = subprocess.run(
        ["mprof", "run", "-o", mem_profile_name, filename],
        capture_output=True,
        text=True,
    )

    peak_mem = parse_peak_memory(mem_profile_name)

    # Print the output of the script
    if mem_result.stdout:
        print("\nScript output:")
        print(mem_result.stdout)
    if mem_result.stderr:
        print("\nScript errors:")
        print(mem_result.stderr)

    # Generate memory usage graph
    subprocess.run(
        ["mprof", "plot", "-o", mem_plot_name, "-t", title, mem_profile_name]
    )

    # ======================== CPU ========================
    # Measure runtime separately (more accurate without memory profiling overhead)
    print("\nTiming and profiling execution...")
    start_time = time.time()
    result = subprocess.run(
        [
            "py-spy",
            "record",
            "-o",
            flamegraph_name,
            "--",
            "python",
            filename,
            f"# commit {commit_hash}",
        ],
        capture_output=True,
        text=True,
    )

    end_time = time.time()
    runtime = end_time - start_time

    # Print the output of the script
    if result.stdout:
        print("\nScript output:")
        print(result.stdout)
    if result.stderr:
        print("\nScript errors:")
        print(result.stderr)

    profile_summary = {
        base_name: {
            "timestamp": time.time(),
            "runtime (s)": runtime,
            "peak_memory (MB)": peak_mem,
            "flamegraph": flamegraph_name.replace("results/", ""),
            "memplot": mem_plot_name.replace("results/", ""),
            "memprofile": mem_profile_name.replace("results/", ""),
        }
    }

    write_json(json_name, profile_summary)

    if result.stderr == "Error: No child process (os error 10)":
        return 0
    else:
        return result.returncode


def write_json(json_file, data: dict):
    path = Path(json_file)

    # If file exists, load its content and merge with profile_summary
    if path.exists():
        with open(json_file, "r") as f:
            existing_data = json.load(f)

        merged_data = {**existing_data, **data}

        # Write the merged data back to the file
        with open(json_file, "w") as f:
            json.dump(merged_data, f, indent=4)
    else:
        with open(json_file, "w") as f:
            json.dump(data, f, indent=4)


def parse_peak_memory(memprofile):
    max_value = None

    with open(memprofile, "r") as file:
        for line in file:
            if line.startswith("MEM"):
                parts = line.split()
                if len(parts) >= 3:  # Ensure line has at least 3 parts
                    try:
                        current_value = float(parts[1])
                        if max_value is None or current_value > max_value:
                            max_value = current_value
                    except ValueError:
                        # Skip lines where the value can't be converted to float
                        continue

    return max_value


def get_git_short_hash():
    try:
        # Get the short (7-character) Git commit hash
        commit_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return commit_hash
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profile a Python script's execution.")
    parser.add_argument("filename", help="The Python file to profile")
    args = parser.parse_args()

    # Check if memory_profiler is available
    try:
        import memory_profiler
    except ImportError:
        print(
            "Error: memory_profiler package is required. Install with: pip install memory-profiler",
            file=sys.stderr,
        )
        sys.exit(1)

    profile_python_file(args.filename)
    sys.exit()  # TODO: exit with error code
