import json
import sys

import click


GREEN = "\033[32m"
DIM = "\033[2m"
BOLD = "\033[1m"
RED = "\033[91m"
RESET = "\033[0m"

FILE_TOOLS = {"Read", "Write", "Edit", "MultiEdit"}


def format_stream_line(line: str) -> str | None:
    """Parse a single JSON stream line and return formatted output, or None."""
    line = line.strip()
    if not line:
        return None

    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        return None

    msg_type = d.get("type", "")

    if msg_type == "assistant":
        content = d.get("message", {}).get("content", [])
        parts = []
        for item in content:
            if item.get("type") == "tool_use":
                name = item.get("name", "")
                inp = item.get("input", {})
                if name in FILE_TOOLS:
                    parts.append(f"  {GREEN}->{RESET} {name}: {inp.get('file_path', '')}")
                elif name == "Bash":
                    parts.append(f"  {GREEN}->{RESET} Bash: {inp.get('command', '')[:80]}")
                else:
                    parts.append(f"  {GREEN}->{RESET} {name}")
        if parts:
            return "\n".join(parts)

    elif msg_type == "result":
        is_error = d.get("is_error", False)
        duration = d.get("duration_ms", 0) // 1000
        cost = d.get("total_cost_usd", 0)
        status = f"{RED}FAILED{RESET}" if is_error else f"{GREEN}SUCCESS{RESET}"
        return f"\n{BOLD}Result: {status}{RESET}\n{DIM}  {duration}s | ${cost:.4f}{RESET}"

    return None


def process_stream(input_stream=None):
    """Read lines from input stream and print formatted output."""
    if input_stream is None:
        input_stream = sys.stdin
    for line in input_stream:
        output = format_stream_line(line)
        if output:
            click.echo(output)
