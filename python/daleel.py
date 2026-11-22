"""Read approved accounting records through a read-only SQLite connection."""
import argparse
import json
import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
import re


QUERIES = {
    "accounts": """
        SELECT code, name, kind, currency
        FROM daleel_accounts ORDER BY code LIMIT 501
    """,
    "cashboxes": """
        SELECT code, name, account_code, currency
        FROM daleel_cashboxes ORDER BY code LIMIT 501
    """,
    "trial-balance": """
        SELECT account_code, currency, debit, credit
        FROM daleel_trial_balance
        WHERE start_date = ? AND end_date = ?
        ORDER BY account_code, currency LIMIT 501
    """,
}


def money(value):
    if not isinstance(value, str) or len(value) > 40 or not re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("يجب أن يصدّر الموصل المبالغ كنص عشري دقيق.")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError("وجدت مبلغًا غير صالح في المصدر.") from None
    if not number.is_finite() or abs(number) >= Decimal("1e24") or number.as_tuple().exponent < -12:
        raise ValueError("وجدت مبلغًا خارج نطاق الدقة المدعوم.")
    return number


def summarize_balance(rows):
    totals = {}
    seen = set()
    with localcontext() as context:
        context.prec = 50
        for row in rows:
            currency = row["currency"]
            if not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
                raise ValueError("وجدت صفًا بلا رمز عملة صالح.")
            if not isinstance(row["account_code"], str) or not row["account_code"].strip():
                raise ValueError("وجدت صفًا بلا رمز حساب.")
            key = (row["account_code"], currency)
            if key in seen:
                raise ValueError("وجدت صفوفًا مكررة للحساب نفسه والعملة نفسها.")
            seen.add(key)
            debit, credit = totals.get(currency, (Decimal(0), Decimal(0)))
            totals[currency] = debit + money(row["debit"]), credit + money(row["credit"])
        return [
            {"currency": currency, "debit": format(debit, "f"), "credit": format(credit, "f"),
             "difference": format(debit - credit, "f"), "balanced": debit == credit}
            for currency, (debit, credit) in sorted(totals.items())
        ]


def read_records(database, source_label, task, start=None, end=None):
    path = Path(database).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("حدد ملف SQLite صالحًا.")
    if task == "trial-balance":
        try:
            valid = (start and end and date.fromisoformat(start).isoformat() == start
                     and date.fromisoformat(end).isoformat() == end and start <= end)
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("حدد بداية ونهاية فترة صحيحتين بصيغة YYYY-MM-DD.")
    elif start or end:
        raise ValueError("خيارات الفترة مخصصة لميزان المراجعة.")
    parameters = (start, end) if task == "trial-balance" else ()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("PRAGMA query_only=ON")
        connection.set_progress_handler(lambda: 1, 2_000_000)
        rows = [dict(row) for row in connection.execute(QUERIES[task], parameters)]
    complete = len(rows) <= 500
    rows = rows[:500]
    if any(not isinstance(value, str) or len(value) > 512 for row in rows for value in row.values()):
        raise ValueError("يحتوي المصدر على قيمة فارغة أو نوع بيانات لا يطابق مخطط دليل.")
    if task == "trial-balance":
        for row in rows:
            money(row["debit"])
            money(row["credit"])
    result = {
        "source": {"label": source_label, "object": "daleel_" + task.replace("-", "_"),
                   "read_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "task": task,
        "status": "empty" if not rows else ("complete" if complete else "truncated"),
        "rows_returned": len(rows),
        "rows": rows,
    }
    if task == "trial-balance":
        result["period"] = {"start": start, "end": end}
        result["totals_by_currency"] = summarize_balance(rows) if complete and rows else None
    return result


def main():
    parser = argparse.ArgumentParser(description="دليل | قراءة بيانات محاسبية مصرح بها")
    parser.add_argument("--database", required=True, help="ملف SQLite مصرح بقراءته")
    parser.add_argument("--source-label", required=True, help="اسم يحدد المصدر في نتائج القراءة")
    parser.add_argument("--approved", action="store_true", help="تأكيد الإذن بقراءة هذا المصدر")
    parser.add_argument("task", choices=QUERIES)
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()
    if not args.approved or not args.source_label.strip():
        parser.error("يلزم تأكيد الإذن وتحديد اسم المصدر.")
    try:
        result = read_records(args.database, args.source_label, args.task, args.start, args.end)
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"تعذرت القراءة: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
