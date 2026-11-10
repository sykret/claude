"""Command-line entry point for sfit."""

import argparse
from typing import Optional, Sequence

from sfit import __version__


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="sfit", description="sfit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.parse_args(argv)
    print("sfit is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
