"""Operator-owned procedure memory. Accounting records stay in the source file."""
from contextlib import closing, contextmanager
import os
from pathlib import Path
import sqlite3


ROLES = {"accounting", "engineering", "legal"}


class Workspace:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        if not self.path.exists():
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                pass
            else:
                os.close(descriptor)
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS procedures (
                    id INTEGER PRIMARY KEY, role TEXT NOT NULL,
                    title TEXT NOT NULL, steps TEXT NOT NULL, reference TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usage (
                    task TEXT PRIMARY KEY, uses INTEGER NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        with closing(sqlite3.connect(self.path, timeout=2)) as connection, connection:
            connection.row_factory = sqlite3.Row
            yield connection

    def snapshot(self):
        with self.connect() as connection:
            procedures = [dict(row) for row in connection.execute(
                "SELECT id, role, title, steps, reference FROM procedures ORDER BY id DESC"
            )]
            suggestion = connection.execute(
                "SELECT task FROM usage ORDER BY uses DESC, task LIMIT 1"
            ).fetchone()
        return {"enabled": True, "procedures": procedures, "suggestion": suggestion["task"] if suggestion else None}

    def record_usage(self, task):
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO usage(task, uses) VALUES (?, 1)
                ON CONFLICT(task) DO UPDATE SET uses = uses + 1
            """, (task,))

    def save(self, request):
        role = request.get("role")
        if not isinstance(role, str) or role not in ROLES:
            raise ValueError("اختر مجال الإجراء.")
        fields = []
        for key, limit in (("title", 100), ("steps", 1200), ("reference", 240)):
            value = request.get(key)
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError("أكمل عنوان الإجراء وخطواته ومرجع المراجعة ضمن الحجم المسموح.")
            fields.append(value.strip())
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT count(*) FROM procedures").fetchone()[0] >= 100:
                raise ValueError("بلغت مساحة العمل حد 100 إجراء. احذف إجراءً غير مستخدم لإضافة آخر.")
            connection.execute("INSERT INTO procedures(role, title, steps, reference) VALUES (?, ?, ?, ?)",
                               (role, *fields))

    def delete(self, procedure_id):
        if type(procedure_id) is not int or not 1 <= procedure_id <= (1 << 63) - 1:
            raise ValueError("رقم الإجراء غير صالح.")
        with self.connect() as connection:
            connection.execute("DELETE FROM procedures WHERE id = ?", (procedure_id,))

    def clear_usage(self):
        with self.connect() as connection:
            connection.execute("DELETE FROM usage")
