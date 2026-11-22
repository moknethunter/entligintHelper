"""Entry point for the portable Windows executable."""
import os
from pathlib import Path
import sys

from desk import main


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and not stream.isatty():
            stream.reconfigure(encoding="utf-8", errors="replace")
    state = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Daleel"
    state.mkdir(parents=True, exist_ok=True)
    if len(sys.argv) == 1:
        sys.argv.extend(["--demo", "--workspace", str(state / "demo.db")])
    elif len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        source = Path(sys.argv.pop())
        sys.argv.extend(["--database", str(source), "--source-label", source.name,
                         "--approved", "--workspace", str(state / "work.db")])
    sys.argv.append("--open-browser")
    raise SystemExit(main())
