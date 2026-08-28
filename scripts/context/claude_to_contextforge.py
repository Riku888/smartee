import argparse
import json
from pathlib import Path
from typing import Any

CONTEXT_USAGE_PREFIX = "## Context Usage"


def text_from_blocks(blocks: list[Any]) -> str:
    """Extract useful visible text from Claude content blocks.

    Intentionally excludes:
    - private thinking
    - redacted thinking
    - tool_use instructions

    Tool results are preserved because they may contain useful evidence
    from commands, tests, file reads, or other tools.
    """
    parts: list[str] = []

    for block in blocks:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")

        if block_type == "text":
            text = block.get("text")

            if isinstance(text, str):
                text = text.strip()

                if text:
                    parts.append(text)

        elif block_type == "tool_result":
            content = block.get("content")

            if isinstance(content, str):
                content = content.strip()

                if content:
                    parts.append(content)

            elif isinstance(content, list):
                nested_text = text_from_blocks(content).strip()

                if nested_text:
                    parts.append(nested_text)

        # Deliberately excluded:
        #
        # thinking
        # redacted_thinking
        # tool_use
        #
        # We want durable working context, not Claude's private reasoning
        # or the raw tool invocation itself.

    return "\n\n".join(parts)


def is_generated_meta_message(obj: dict[str, Any], content: str) -> bool:
    """Return True for Claude-generated UI/meta content we do not want."""
    if obj.get("isMeta") is True:
        return True

    # Defensive fallback in case Claude Code emits this diagnostic
    # without setting isMeta in a future transcript version.
    return content.startswith(CONTEXT_USAGE_PREFIX)


def convert_record(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert one Claude JSONL record into ContextForge trace items."""
    message = obj.get("message")

    if not isinstance(message, dict):
        return []

    role = message.get("role")
    content = message.get("content")

    if role not in {"user", "assistant"}:
        return []

    # Simple string message.
    if isinstance(content, str):
        content = content.strip()

        if not content:
            return []

        if is_generated_meta_message(obj, content):
            return []

        return [
            {
                "role": role,
                "kind": "message",
                "content": content,
            }
        ]

    # Claude structured content blocks.
    if not isinstance(content, list):
        return []

    items: list[dict[str, Any]] = []

    # User records can contain both normal text and tool_result blocks.
    if role == "user":
        normal_parts: list[str] = []

        for block in content:
            if not isinstance(block, dict):
                continue

            block_type = block.get("type")

            if block_type == "text":
                text = block.get("text")

                if isinstance(text, str):
                    text = text.strip()

                    if text and not is_generated_meta_message(obj, text):
                        normal_parts.append(text)

            elif block_type == "tool_result":
                result_content = block.get("content")
                result_text = ""

                if isinstance(result_content, str):
                    result_text = result_content.strip()

                elif isinstance(result_content, list):
                    result_text = text_from_blocks(result_content).strip()

                if result_text:
                    items.append(
                        {
                            "role": "tool",
                            "kind": "tool_result",
                            "content": result_text,
                        }
                    )

        if normal_parts:
            items.insert(
                0,
                {
                    "role": "user",
                    "kind": "message",
                    "content": "\n\n".join(normal_parts),
                },
            )

        return items

    # Assistant records:
    # keep only visible assistant text.
    # thinking and raw tool_use blocks are intentionally excluded.
    assistant_text = text_from_blocks(content).strip()

    if not assistant_text:
        return []

    if is_generated_meta_message(obj, assistant_text):
        return []

    return [
        {
            "role": "assistant",
            "kind": "message",
            "content": assistant_text,
        }
    ]


def convert_transcript(input_path: Path) -> dict[str, Any]:
    """Convert a Claude Code JSONL transcript into a ContextForge trace."""
    items: list[dict[str, Any]] = []
    invalid_json_lines = 0

    with input_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                invalid_json_lines += 1
                print(f"Skipping invalid JSON on line {line_number}")
                continue

            if not isinstance(obj, dict):
                continue

            items.extend(convert_record(obj))

    return {"items": items}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a Claude Code JSONL transcript into a ContextForge trace."
        )
    )

    parser.add_argument(
        "transcript",
        type=Path,
        help="Path to the Claude Code .jsonl transcript.",
    )

    parser.add_argument(
        "output",
        type=Path,
        help="Path for the generated ContextForge JSON trace.",
    )

    args = parser.parse_args()

    transcript_path = args.transcript.expanduser().resolve()
    output_path = args.output.expanduser()

    if not transcript_path.exists():
        raise SystemExit(f"Transcript not found: {transcript_path}")

    if not transcript_path.is_file():
        raise SystemExit(f"Transcript is not a file: {transcript_path}")

    trace = convert_transcript(transcript_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            trace,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(f"Input:  {transcript_path}")
    print(f"Output: {output_path}")
    print(f"Items:  {len(trace['items'])}")


if __name__ == "__main__":
    main()
