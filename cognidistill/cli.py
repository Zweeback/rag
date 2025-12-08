"""Simple command line interface for CogniDistill."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .system import CogniDistillSystem


def run_cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CogniDistill Wissenssystem")
    parser.add_argument("command", nargs="?", help="Direktbefehl wie /statistik oder /frage ...")
    parser.add_argument(
        "text",
        nargs=argparse.REMAINDER,
        help="Zusätzlicher Text für den Befehl, z.B. die Frage oder der zu ladende Inhalt.",
    )
    args = parser.parse_args(argv)

    system = CogniDistillSystem()
    if args.command:
        payload = " ".join([args.command] + args.text).strip()
        print(system.handle_command(payload))
        return 0

    print(system.start_message())
    try:
        while True:
            try:
                command = input("> ")
            except EOFError:
                break
            if command.lower() in {"/exit", "quit", "q"}:
                break
            output = system.handle_command(command)
            print(output)
    except KeyboardInterrupt:
        print("\nBeendet.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run_cli())
