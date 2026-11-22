"""Compare two literal document versions without retaining their contents."""
from difflib import SequenceMatcher


OPERATIONS = {"insert", "delete", "replace"}


def compare_documents(request):
    if set(request) != {"before", "after"}:
        raise ValueError("أرفق نسختين نصيتين للمقارنة.")
    versions = []
    for key in ("before", "after"):
        text = request[key]
        if not isinstance(text, str) or len(text.encode("utf-8")) > 32768 or "\x00" in text:
            raise ValueError("يدعم كل ملف نصيًا بترميز UTF-8 وبحجم حتى 32 كيلوبايت.")
        lines = text.splitlines()
        if len(lines) > 1600:
            raise ValueError("يدعم كل ملف حتى 1600 سطر.")
        versions.append(lines)
    before, after = versions
    changes = []
    counts = dict.fromkeys(sorted(OPERATIONS), 0)
    matcher = SequenceMatcher(None, before, after, autojunk=False)
    for operation, a_start, a_end, b_start, b_end in matcher.get_opcodes():
        if operation == "equal":
            continue
        counts[operation] += 1
        changes.append({"operation": operation, "before_start": a_start + 1, "after_start": b_start + 1,
                        "before_lines": before[a_start:a_end], "after_lines": after[b_start:b_end]})
    return {"before_line_count": len(before), "after_line_count": len(after),
            "counts": counts, "changes": changes}
