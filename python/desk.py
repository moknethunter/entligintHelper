"""Run Daleel's single-operator workspace on the loopback interface."""
import argparse
from contextlib import closing
from hmac import compare_digest
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from secrets import token_urlsafe
import sqlite3
from tempfile import TemporaryDirectory

from daleel import QUERIES, read_records
from review import compare_documents
from workspace import Workspace


WEB = Path(__file__).resolve().parent / "web"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
LOOPBACK = "127.0.0.1"


class DeskServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, database, source_label, demo, workspace=None):
        self.token = token_urlsafe(32)
        self.database = database
        self.source_label = source_label
        self.demo = demo
        self.workspace = workspace
        super().__init__((LOOPBACK, port), DeskHandler)
        self.host_header = f"{LOOPBACK}:{self.server_port}"
        self.origin = f"http://{self.host_header}"

    def get_request(self):
        client, address = super().get_request()
        client.settimeout(8)
        return client, address


class DeskHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, payload):
        self.respond(status, "application/json; charset=utf-8",
                     json.dumps(payload, ensure_ascii=False, allow_nan=False).encode())

    def check_host(self):
        if self.headers.get_all("Host") == [self.server.host_header]:
            return True
        self.send_json(HTTPStatus.FORBIDDEN, {"error": "عنوان الاتصال المحلي غير مطابق."})
        return False

    def do_GET(self):
        if not self.check_host():
            return
        asset = ASSETS.get(self.path)
        if not asset:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "الصفحة المطلوبة غير متاحة."})
            return
        filename, content_type = asset
        self.respond(HTTPStatus.OK, content_type, (WEB / filename).read_bytes())

    def do_POST(self):
        if not self.check_host():
            return
        if self.path not in {"/api/source", "/api/report", "/api/workspace", "/api/review"}:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "الطلب غير متاح."})
            return
        auth = self.headers.get("Authorization", "").encode("latin-1")
        expected = f"Bearer {self.server.token}".encode()
        if (self.headers.get_all("Origin") != [self.server.origin]
                or not compare_digest(auth, expected)):
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "افتح رابط الجلسة الذي يظهر في نافذة التشغيل."})
            return
        if self.headers.get_content_type() != "application/json":
            self.send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "صيغة الطلب غير مدعومة."})
            return
        try:
            sizes = self.headers.get_all("Content-Length") or []
            if self.headers.get("Transfer-Encoding") or len(sizes) != 1 or not sizes[0].isdecimal():
                raise ValueError
            size = int(sizes[0])
            limit = 524288 if self.path == "/api/review" else 8192
            if not 0 < size <= limit:
                raise ValueError
            request = json.loads(self.rfile.read(size))
            if not isinstance(request, dict):
                raise ValueError
        except (ValueError, RecursionError, TimeoutError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "تعذرت قراءة بيانات الطلب."})
            return

        if self.path == "/api/source":
            self.send_json(HTTPStatus.OK, {"label": self.server.source_label, "demo": self.server.demo})
            return
        if self.path == "/api/review":
            try:
                self.send_json(HTTPStatus.OK, compare_documents(request))
            except ValueError as error:
                self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
            return
        if self.path == "/api/workspace":
            self.handle_workspace(request)
            return
        report_fields = {key: value for key, value in request.items() if key != "learn"}
        if (set(report_fields) - {"task", "start", "end"}
                or any(not isinstance(v, str) for v in report_fields.values())
                or type(request.get("learn", False)) is not bool):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "حقول الطلب غير صالحة."})
            return
        task = request.get("task")
        if task not in QUERIES:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "اختر تقريرًا يدعمه التطبيق."})
            return
        try:
            report = read_records(self.server.database, self.server.source_label, task,
                                  request.get("start"), request.get("end"))
            if self.server.workspace and request.get("learn") and report["status"] == "complete":
                try:
                    self.server.workspace.record_usage(task)
                except sqlite3.Error:
                    report["learning_error"] = True
            self.send_json(HTTPStatus.OK, report)
        except ValueError as error:
            self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
        except (OSError, sqlite3.Error):
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "error": "تعذرت قراءة المصدر. تحقق من توفر الملف ومطابقة مخطط البيانات."
            })


    def handle_workspace(self, request):
        workspace = self.server.workspace
        action = request.get("action")
        if workspace is None:
            self.send_json(HTTPStatus.OK, {"enabled": False})
            return
        try:
            if action == "save":
                workspace.save(request)
            elif action == "delete":
                workspace.delete(request.get("id"))
            elif action == "clear-usage":
                workspace.clear_usage()
            elif action != "read":
                raise ValueError("عملية الذاكرة غير مدعومة.")
            self.send_json(HTTPStatus.OK, workspace.snapshot())
        except ValueError as error:
            self.send_json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(error)})
        except (OSError, sqlite3.Error):
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "تعذر الوصول إلى ملف ذاكرة الإجراءات."})


def create_demo(database):
    script = Path(__file__).with_name("demo.sql").read_text(encoding="utf-8")
    with closing(sqlite3.connect(database)) as connection:
        connection.executescript(script)


def main():
    parser = argparse.ArgumentParser(description="دليل | مساحة العمل المحاسبية")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true")
    mode.add_argument("--database", type=Path)
    parser.add_argument("--source-label")
    parser.add_argument("--approved", action="store_true")
    parser.add_argument("--open-browser", action="store_true", help="فتح المتصفح المحلي بعد التشغيل")
    parser.add_argument("--workspace", type=Path, help="ملف مستقل لحفظ إجراءات الفريق وتفضيلات الاستخدام")
    parser.add_argument("--port", type=int, default=0, help="رقم المنفذ المحلي، 0 يختار منفذًا متاحًا")
    options = parser.parse_args()
    if not 0 <= options.port <= 65535:
        parser.error("رقم المنفذ خارج النطاق.")
    if not options.demo and (not options.approved or not (options.source_label or "").strip()):
        parser.error("يلزم تحديد اسم المصدر والإقرار بتفويض القراءة.")
    if options.database and not options.database.is_file():
        parser.error("ملف المصدر غير موجود.")
    try:
        with TemporaryDirectory(prefix="daleel-") as temporary:
            database = options.database
            label = options.source_label
            if options.demo:
                database = Path(temporary) / "demo.db"
                create_demo(database)
                label = "دفتر المحاسبة التجريبي"
            if options.workspace and (options.workspace.resolve() == database.resolve() or
                                      (options.workspace.exists() and options.workspace.samefile(database))):
                parser.error("استخدم ملفًا منفصلًا لذاكرة الإجراءات.")
            workspace_path = options.workspace or (Path(temporary) / "workspace.db" if options.demo else None)
            workspace = Workspace(workspace_path) if workspace_path else None
            with DeskServer(options.port, database.resolve(), label, options.demo, workspace) as server:
                print("افتح رابط الجلسة في متصفح هذا الكمبيوتر:", flush=True)
                url = f"{server.origin}/#{server.token}"
                print(url, flush=True)
                if options.open_browser:
                    import webbrowser
                    try:
                        webbrowser.open(url)
                    except (OSError, webbrowser.Error):
                        pass
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    return 0
    except (OSError, sqlite3.Error):
        parser.exit(1, "تعذر تشغيل مساحة العمل المحلية. تحقق من المنفذ وملف البيانات.\n")


if __name__ == "__main__":
    raise SystemExit(main())
