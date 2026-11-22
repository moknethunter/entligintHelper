import hashlib
import http.client
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from daleel import read_records, summarize_balance
from desk import DeskServer, create_demo
from workspace import Workspace


class DeskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.database = Path(cls.temporary.name) / "source.db"
        create_demo(cls.database)
        cls.workspace_file = Path(cls.temporary.name) / "preferences.db"
        cls.server = DeskServer(0, cls.database, "Test source", True, Workspace(cls.workspace_file))
        cls.addClassCleanup(cls.server.server_close)
        worker = Thread(target=cls.server.serve_forever, daemon=True)
        worker.start()
        cls.addClassCleanup(worker.join, 2)
        cls.addClassCleanup(cls.server.shutdown)

    def request(self, method="POST", path="/api/report", payload=None, **overrides):
        headers = {
            "Host": self.server.host_header,
            "Origin": self.server.origin,
            "Authorization": "Bearer " + self.server.token,
            "Content-Type": "application/json",
        }
        headers.update(overrides)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            data = None if method == "GET" else json.dumps(payload or {})
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            content = response.read()
            if response.getheader("Content-Type").startswith("application/json"):
                content = json.loads(content)
            return response.status, response.headers, content
        finally:
            connection.close()

    def test_load_workspace(self):
        code, headers, content = self.request(method="GET", path="/")
        self.assertEqual(code, 200)
        self.assertIn(b"/app.js", content)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(self.request(method="GET", path="/../desk.py")[0], 404)

    def test_source_requires_session_and_local_origin(self):
        self.assertEqual(self.request(path="/api/source", Authorization="Bearer invalid")[0], 403)
        self.assertEqual(self.request(path="/api/source", Origin="https://other.example")[0], 403)
        self.assertEqual(self.request(path="/api/source", Host="other.example")[0], 403)
        self.assertEqual(self.request(path="/api/source")[2], {"label": "Test source", "demo": True})

    def test_report_provenance_and_totals(self):
        before = hashlib.sha256(self.database.read_bytes()).digest()
        payload = {"task": "trial-balance", "start": "2026-11-01", "end": "2026-11-30"}
        code, _, result = self.request(payload=payload)
        self.assertEqual(code, 200)
        self.assertEqual(result["source"]["object"], "daleel_trial_balance")
        self.assertEqual(result["period"]["start"], "2026-11-01")
        self.assertEqual(result["totals_by_currency"], [{
            "currency": "YER", "debit": "125000.25", "credit": "125000.25",
            "difference": "0.00", "balanced": True,
        }])
        self.assertEqual(hashlib.sha256(self.database.read_bytes()).digest(), before)

    def test_invalid_or_missing_reports(self):
        self.assertEqual(self.request(payload={"task": "custom", "sql": "SELECT 1"})[0], 400)
        self.assertEqual(self.request(payload={"task": "trial-balance", "start": "2026-02-30", "end": "2026-03-01"})[0], 422)
        result = self.request(payload={"task": "trial-balance", "start": "2025-01-01", "end": "2025-01-31"})[2]
        self.assertEqual((result["status"], result["totals_by_currency"]), ("empty", None))

    def test_account_and_cashbox_reports(self):
        for task, count in (("accounts", 2), ("cashboxes", 1)):
            code, _, result = self.request(payload={"task": task})
            self.assertEqual((code, result["status"], result["rows_returned"]), (200, "complete", count))


    def test_review_returns_source_line_numbers_and_does_not_store_documents(self):
        payload = {"before": "Delivery\nUse version 1\nReview", "after": "Delivery\nUse version 2\nReview"}
        code, _, report = self.request(path="/api/review", payload=payload)
        self.assertEqual(code, 200)
        self.assertEqual(report["counts"], {"delete": 0, "insert": 0, "replace": 1})
        self.assertEqual(report["changes"], [{
            "operation": "replace", "before_start": 2, "after_start": 2,
            "before_lines": ["Use version 1"], "after_lines": ["Use version 2"],
        }])
        self.assertNotIn(b"Use version", self.workspace_file.read_bytes())
        self.assertEqual(self.request(path="/api/review", payload={"before": "x" * 32769, "after": ""})[0], 422)

    def test_procedures_persist_and_can_be_removed(self):
        self.assertEqual(self.request(path="/api/workspace", payload={"action": "save", "role": "manager"})[0], 422)
        payload = {"action": "save", "role": "engineering", "title": "Review delivery",
                   "steps": "Check revision and requirements", "reference": "Delivery spec v2"}
        self.assertEqual(self.request(path="/api/workspace", payload=payload, Authorization="Bearer invalid")[0], 403)
        code, _, result = self.request(path="/api/workspace", payload=payload)
        self.assertEqual(code, 200)
        saved = result["procedures"][0]
        self.assertEqual(Workspace(self.workspace_file).snapshot()["procedures"], [saved])
        removal = {"action": "delete", "id": saved["id"]}
        self.assertEqual(self.request(path="/api/workspace", payload=removal)[2]["procedures"], [])

    def test_learning_is_opt_in_and_records_only_report_type(self):
        self.server.workspace.clear_usage()
        self.request(payload={"task": "accounts"})
        self.assertIsNone(self.server.workspace.snapshot()["suggestion"])
        self.request(payload={"task": "cashboxes", "learn": True})
        self.assertEqual(Workspace(self.workspace_file).snapshot()["suggestion"], "cashboxes")
        with self.server.workspace.connect() as connection:
            self.assertEqual([tuple(row) for row in connection.execute("SELECT * FROM usage")], [("cashboxes", 1)])
        self.request(path="/api/workspace", payload={"action": "clear-usage"})
        self.assertIsNone(self.server.workspace.snapshot()["suggestion"])


class AccountingTests(unittest.TestCase):
    def test_decimal_currency_totals_remain_independent(self):
        result = summarize_balance([
            {"account_code": "a", "currency": "USD", "debit": "0.1", "credit": "0.30"},
            {"account_code": "b", "currency": "USD", "debit": "0.2", "credit": "0"},
            {"account_code": "a", "currency": "YER", "debit": "0", "credit": "1.20"},
        ])
        self.assertEqual([(row["currency"], row["difference"], row["balanced"]) for row in result],
                         [("USD", "0.00", True), ("YER", "-1.20", False)])

    def test_truncated_trial_balance_has_no_totals(self):
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "truncated.db"
            create_demo(database)
            period = ("2026-11-01", "2026-11-30")
            connection = sqlite3.connect(database)
            try:
                connection.executemany("INSERT INTO daleel_trial_balance VALUES (?,?,?,?,?,?)",
                                       [(*period, str(i), "YER", "1", "0") for i in range(501)])
                connection.commit()
            finally:
                connection.close()
            result = read_records(database, "Test source", "trial-balance", *period)
            self.assertEqual((result["status"], result["rows_returned"], result["totals_by_currency"]),
                             ("truncated", 500, None))
