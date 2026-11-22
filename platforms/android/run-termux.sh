#!/data/data/com.termux/files/usr/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -f "$ROOT/python/desk.py" ]; then
    ROOT=$(CDPATH= cd -- "$ROOT/../.." && pwd)
fi

if ! command -v python >/dev/null 2>&1; then
    printf '%s\n' 'Install Python in Termux with: pkg install python' >&2
    exit 1
fi

STATE="${HOME:?}/.daleel"
umask 077
mkdir -p "$STATE"
if [ "$#" -eq 0 ]; then
    set -- --demo --workspace "$STATE/demo.db"
elif [ "$#" -eq 1 ]; then
    SOURCE=$1
    set -- --database "$SOURCE" --source-label "$(basename -- "$SOURCE")" --approved --workspace "$STATE/work.db"
else
    printf '%s\n' 'Usage: sh run-termux.sh [authorized-sqlite-file]' >&2
    exit 1
fi
exec python -B "$ROOT/python/desk.py" "$@"
