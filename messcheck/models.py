"""Data access and small domain helpers built on top of :mod:`messcheck.db`."""

from collections import OrderedDict
from datetime import datetime

from .constants import DEFAULT_CATEGORIES
from .db import execute, get_db, query

TRUTHY = {"yes", "on", "1", "true"}


# --------------------------------------------------------------------------
# Fields
# --------------------------------------------------------------------------

def list_fields():
    return query(
        "SELECT * FROM fields ORDER BY category COLLATE NOCASE, position, id"
    )


def get_field(field_id):
    return query("SELECT * FROM fields WHERE id = ?", (field_id,), one=True)


def create_field(name, field_type, category):
    row = query(
        "SELECT COALESCE(MAX(position), -1) + 1 AS pos FROM fields WHERE category = ?",
        (category,),
        one=True,
    )
    return execute(
        "INSERT INTO fields (name, field_type, category, position, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (name, field_type, category, row["pos"], _now()),
    ).lastrowid


def update_field(field_id, name, field_type, category):
    execute(
        "UPDATE fields SET name = ?, field_type = ?, category = ? WHERE id = ?",
        (name, field_type, category, field_id),
    )


def delete_field(field_id):
    execute("DELETE FROM checklist_fields WHERE field_id = ?", (field_id,))
    execute("DELETE FROM fields WHERE id = ?", (field_id,))


def move_field(field_id, direction):
    """Swap a field with its neighbour inside the same category.

    Returns True when something moved, so the caller can flash the right
    message for a field that is already at the top or bottom.
    """
    field = get_field(field_id)
    if field is None:
        return False
    siblings = query(
        "SELECT id FROM fields WHERE category = ? ORDER BY position, id",
        (field["category"],),
    )
    ids = [row["id"] for row in siblings]
    index = ids.index(field["id"])
    target = index - 1 if direction == "up" else index + 1
    if target < 0 or target >= len(ids):
        return False
    ids[index], ids[target] = ids[target], ids[index]
    db = get_db()
    db.executemany(
        "UPDATE fields SET position = ? WHERE id = ?",
        [(pos, fid) for pos, fid in enumerate(ids)],
    )
    db.commit()
    return True


def group_by_category(fields):
    """Group fields into an ordered mapping, known categories first."""
    grouped = OrderedDict()
    for name in DEFAULT_CATEGORIES:
        grouped[name] = []
    for field in fields:
        grouped.setdefault(field["category"], []).append(field)
    return OrderedDict((k, v) for k, v in grouped.items() if v)


def all_categories():
    """Every category in use, plus the suggested defaults, sorted."""
    used = {row["category"] for row in query("SELECT DISTINCT category FROM fields")}
    return sorted(used | set(DEFAULT_CATEGORIES), key=str.lower)


# --------------------------------------------------------------------------
# Inspections (the `checklist` table)
# --------------------------------------------------------------------------

def list_records(search="", date_from="", date_to=""):
    sql = "SELECT * FROM checklist WHERE 1 = 1"
    args = []
    if search:
        sql += " AND inspector_name LIKE ?"
        args.append(f"%{search}%")
    if date_from:
        sql += " AND date >= ?"
        args.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        args.append(date_to)
    sql += " ORDER BY date DESC, time DESC, id DESC"
    return query(sql, args)


def recent_records(limit=5):
    return query(
        "SELECT * FROM checklist ORDER BY date DESC, time DESC, id DESC LIMIT ?",
        (limit,),
    )


def get_record(record_id):
    return query("SELECT * FROM checklist WHERE id = ?", (record_id,), one=True)


def record_values(record_id):
    """Return ``{field_id: {"value": ..., "comment": ...}}`` for one record."""
    rows = query(
        "SELECT field_id, value, comment FROM checklist_fields WHERE checklist_id = ?",
        (record_id,),
    )
    return {
        row["field_id"]: {"value": row["value"], "comment": row["comment"]}
        for row in rows
    }


def create_record(date, time, inspector_name, notes, answers):
    now = _now()
    cur = execute(
        "INSERT INTO checklist (date, time, inspector_name, notes, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (date, time, inspector_name, notes, now, now),
    )
    record_id = cur.lastrowid
    _save_answers(record_id, answers)
    return record_id


def update_record(record_id, date, time, inspector_name, notes, answers):
    execute(
        "UPDATE checklist SET date = ?, time = ?, inspector_name = ?, notes = ?,"
        " updated_at = ? WHERE id = ?",
        (date, time, inspector_name, notes, _now(), record_id),
    )
    _save_answers(record_id, answers)


def delete_record(record_id):
    execute("DELETE FROM checklist_fields WHERE checklist_id = ?", (record_id,))
    execute("DELETE FROM checklist WHERE id = ?", (record_id,))


def _save_answers(record_id, answers):
    """Upsert every answer. Rows absent from ``answers`` are removed, so an
    unticked checkbox or a cleared comment does not linger from a past save."""
    db = get_db()
    db.execute("DELETE FROM checklist_fields WHERE checklist_id = ?", (record_id,))
    db.executemany(
        "INSERT INTO checklist_fields (checklist_id, field_id, value, comment)"
        " VALUES (?, ?, ?, ?)",
        [
            (record_id, field_id, data["value"], data["comment"])
            for field_id, data in answers.items()
        ],
    )
    db.commit()


def parse_answers(form, fields):
    """Read a submitted checklist form into the ``answers`` mapping.

    Checkbox values are stored explicitly as "yes"/"no" rather than relying on
    the browser omitting unticked boxes, so an edit can turn a box off.
    """
    answers = {}
    for field in fields:
        key = str(field["id"])
        comment = (form.get(f"{key}_comment") or "").strip()
        if field["field_type"] == "checkbox":
            value = "yes" if form.get(key) else "no"
        else:
            value = (form.get(key) or "").strip()
        if value or comment:
            answers[field["id"]] = {"value": value, "comment": comment}
    return answers


# --------------------------------------------------------------------------
# Scoring and stats
# --------------------------------------------------------------------------

def score_for(record_id, fields=None):
    """Compliance score for a record: ticked checkboxes over total checkboxes.

    Returns ``(checked, total, percent)``; percent is None when the record has
    no checkbox fields to score.
    """
    fields = fields if fields is not None else list_fields()
    values = record_values(record_id)
    checkboxes = [f for f in fields if f["field_type"] == "checkbox"]
    total = len(checkboxes)
    if not total:
        return 0, 0, None
    checked = sum(
        1
        for f in checkboxes
        if (values.get(f["id"], {}).get("value") or "").lower() in TRUTHY
    )
    return checked, total, round(checked * 100 / total)


def scores_for_records(records, fields=None):
    fields = fields if fields is not None else list_fields()
    return {record["id"]: score_for(record["id"], fields) for record in records}


def dashboard_stats():
    fields = list_fields()
    total_records = query("SELECT COUNT(*) AS n FROM checklist", one=True)["n"]
    month = datetime.now().strftime("%Y-%m")
    this_month = query(
        "SELECT COUNT(*) AS n FROM checklist WHERE date LIKE ?", (f"{month}-%",), one=True
    )["n"]
    latest = query(
        "SELECT * FROM checklist ORDER BY date DESC, time DESC, id DESC LIMIT 1", one=True
    )
    latest_score = score_for(latest["id"], fields)[2] if latest else None
    return {
        "total_records": total_records,
        "this_month": this_month,
        "total_fields": len(fields),
        "categories": len(group_by_category(fields)),
        "latest": latest,
        "latest_score": latest_score,
    }


def _now():
    return datetime.now().isoformat(timespec="seconds")
