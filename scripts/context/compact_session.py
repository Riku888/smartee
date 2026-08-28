import argparse
import json
import subprocess
from pathlib import Path

from claude_to_contextforge import convert_transcript


DEFAULT_CONTEXTFORGE = (
    Path.home()
    / "context-forge"
    / ".venv"
    / "bin"
    / "contextforge"
)

DEFAULT_TRACE_OUTPUT = Path(
    ".local/context/traces/latest.json"
)

DEFAULT_COMPILED_OUTPUT = Path(
    ".local/context/compiled/latest.json"
)


def write_trace(
    transcript_path: Path,
    trace_output: Path,
) -> int:
    """Convert a Claude transcript and write a ContextForge trace."""
    trace = convert_transcript(transcript_path)

    trace_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    trace_output.write_text(
        json.dumps(
            trace,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return len(trace["items"])


def run_command(command: list[str]) -> None:
    """Run a subprocess and fail clearly if it fails."""
    print()
    print("$ " + " ".join(command))

    subprocess.run(
        command,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a Claude Code transcript and compile it "
            "with ContextForge."
        )
    )

    parser.add_argument(
        "transcript",
        type=Path,
        help="Claude Code JSONL transcript.",
    )

    parser.add_argument(
        "--budget",
        type=int,
        default=30_000,
        help="Maximum compiled context tokens. Default: 30000.",
    )

    parser.add_argument(
        "--contextforge",
        type=Path,
        default=DEFAULT_CONTEXTFORGE,
        help="Path to the ContextForge CLI executable.",
    )

    parser.add_argument(
        "--trace-output",
        type=Path,
        default=DEFAULT_TRACE_OUTPUT,
        help="Generated ContextForge trace.",
    )

    parser.add_argument(
        "--compiled-output",
        type=Path,
        default=DEFAULT_COMPILED_OUTPUT,
        help="Compiled ContextForge output.",
    )

    args = parser.parse_args()

    transcript_path = args.transcript.expanduser().resolve()
    contextforge_path = args.contextforge.expanduser().resolve()

    if not transcript_path.is_file():
        raise SystemExit(
            f"Transcript not found: {transcript_path}"
        )

    if not contextforge_path.is_file():
        raise SystemExit(
            f"ContextForge executable not found: "
            f"{contextforge_path}"
        )

    if args.budget <= 0:
        raise SystemExit(
            "--budget must be greater than zero."
        )

    item_count = write_trace(
        transcript_path,
        args.trace_output,
    )

    print(f"Transcript: {transcript_path}")
    print(f"Trace:      {args.trace_output}")
    print(f"Items:      {item_count}")

    # A brand-new Claude session may contain no durable context yet.
    # In that case there is nothing useful to compile.
    if item_count == 0:
        print()
        print(
            "No durable conversation items found. "
            "Skipping ContextForge."
        )
        return

    args.compiled_output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_command(
        [
            str(contextforge_path),
            "score",
            str(args.trace_output),
        ]
    )

    run_command(
        [
            str(contextforge_path),
            "compile",
            str(args.trace_output),
            "--budget",
            str(args.budget),
            "--out",
            str(args.compiled_output),
        ]
    )

    print()
    print("Context compaction complete.")
    print(
        f"Compiled: {args.compiled_output}"
    )


if __name__ == "__main__":
    main()