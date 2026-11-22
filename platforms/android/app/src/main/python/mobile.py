"""Start one on-device Daleel service for the Android launcher."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

from daleel import read_records
from desk import DeskServer, create_demo
from workspace import Workspace


_running = None


def launch(files_dir, cache_dir, source, label):
    global _running

    files = Path(files_dir)
    temp = TemporaryDirectory(prefix="daleel-", dir=cache_dir)
    demo = not source
    try:
        if demo:
            database = Path(temp.name) / "demo.db"
            create_demo(database)
            label = "دفتر المحاسبة التجريبي"
        else:
            database = Path(source)
            read_records(database, label, "accounts")
            read_records(database, label, "cashboxes")
        workspace = Workspace(files / ("demo-workspace.db" if demo else "workspace.db"))
        server = DeskServer(0, database, label, demo, workspace)
    except Exception:
        temp.cleanup()
        raise
    Thread(target=server.serve_forever, daemon=True).start()
    previous = _running
    _running = (server, temp, None if demo else database)
    if previous:
        old_server, old_temp, old_database = previous
        old_server.shutdown()
        old_server.server_close()
        old_temp.cleanup()
        if old_database:
            old_database.unlink(missing_ok=True)
    return f"{server.origin}/#{server.token}"
