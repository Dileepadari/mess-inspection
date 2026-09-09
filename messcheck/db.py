"""SQLite access: connection handling, schema creation and migration.

One connection per request, stored on ``flask.g`` and closed when the request
ends. Rows come back as ``sqlite3.Row`` so templates and views can use column
names instead of positional indexes.
"""

import sqlite3
from datetime import datetime

import click
from flask import current_app, g

from .constants import SEED_FIELDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS fields (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    field_type  TEXT    NOT NULL DEFAULT 'checkbox',
    category    TEXT    NOT NULL DEFAULT 'General',
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS checklist (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    time           TEXT NOT NULL,
    inspector_name TEXT NOT NULL,
    notes          TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS checklist_fields (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_id INTEGER NOT NULL REFERENCES checklist(id) ON DELETE CASCADE,
    field_id     INTEGER NOT NULL REFERENCES fields(id)    ON DELETE CASCADE,
    value        TEXT NOT NULL DEFAULT '',
    comment      TEXT NOT NULL DEFAULT '',
    UNIQUE (checklist_id, field_id)
);

CREATE INDEX IF NOT EXISTS idx_checklist_date  ON checklist(date DESC);
CREATE INDEX IF NOT EXISTS idx_cf_checklist_id ON checklist_fields(checklist_id);
"""


def get_db():
    """Return the request-scoped connection, opening one if needed."""
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    """Run a write statement, commit, and return the cursor."""
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur


def _columns(db, table):
    return {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}


def _table_exists(db, table):
    row = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _migrate(db):
    """Bring a database created by an older version up to the current schema.

    The first release stored comments as extra rows whose ``field_id`` was the
    string ``"<id>_comment"``, and had no uniqueness on (checklist_id,
    field_id). Checkbox values were the raw HTML ``"on"``. This folds all of
    that into the current shape, which is idempotent and safe to run on a
    database that is already current.
    """
    if not _table_exists(db, "checklist_fields"):
        return

    legacy_values = None
    if "comment" not in _columns(db, "checklist_fields"):
        # Collect the old rows before the table is replaced.
        merged = {}
        for row in db.execute("SELECT checklist_id, field_id, value FROM checklist_fields"):
            raw_field = str(row["field_id"])
            is_comment = raw_field.endswith("_comment")
            base = raw_field[: -len("_comment")] if is_comment else raw_field
            if not base.isdigit():
                continue
            key = (row["checklist_id"], int(base))
            entry = merged.setdefault(key, {"value": "", "comment": ""})
            text = row["value"] or ""
            if is_comment:
                entry["comment"] = text
            else:
                entry["value"] = "yes" if text in ("on", "yes", "1", "true") else text
        legacy_values = [
            (cid, fid, data["value"], data["comment"])
            for (cid, fid), data in merged.items()
        ]
        db.execute("ALTER TABLE checklist_fields RENAME TO checklist_fields_legacy")

    for table, column, ddl in (
        ("fields", "position", "ALTER TABLE fields ADD COLUMN position INTEGER NOT NULL DEFAULT 0"),
        ("fields", "created_at", "ALTER TABLE fields ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"),
        ("checklist", "notes", "ALTER TABLE checklist ADD COLUMN notes TEXT NOT NULL DEFAULT ''"),
        ("checklist", "created_at", "ALTER TABLE checklist ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"),
        ("checklist", "updated_at", "ALTER TABLE checklist ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"),
    ):
        if _table_exists(db, table) and column not in _columns(db, table):
            db.execute(ddl)

    db.commit()
    return legacy_values


def _restore_legacy(db, legacy_values):
    """Copy migrated rows into the rebuilt table and drop the old one.

    ``legacy_values`` is None when no rename happened, and an empty list when
    the old table existed but held nothing. The table still has to go in that
    second case, so the drop is not guarded by the row count.
    """
    if legacy_values is None:
        return
    if legacy_values:
        db.executemany(
            "INSERT OR REPLACE INTO checklist_fields (checklist_id, field_id, value, comment)"
            " VALUES (?, ?, ?, ?)",
            legacy_values,
        )
    db.execute("DROP TABLE IF EXISTS checklist_fields_legacy")
    db.commit()


def init_db(db=None):
    """Create the schema (migrating an older database first) and seed fields."""
    own = db is None
    if own:
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.row_factory = sqlite3.Row
    try:
        legacy_values = _migrate(db)
        db.executescript(SCHEMA)
        db.commit()
        _restore_legacy(db, legacy_values)
        seed_fields(db)
    finally:
        if own:
            db.close()


def seed_fields(db):
    """Insert the default checklist fields, but only into an empty table."""
    count = db.execute("SELECT COUNT(*) AS n FROM fields").fetchone()[0]
    if count:
        return
    now = datetime.now().isoformat(timespec="seconds")
    db.executemany(
        "INSERT INTO fields (name, field_type, category, position, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (name, ftype, category, index, now)
            for index, (name, ftype, category) in enumerate(SEED_FIELDS)
        ],
    )
    db.commit()


@click.command("init-db")
def init_db_command():
    """Flask CLI: create or upgrade the database, then seed default fields."""
    init_db()
    click.echo(f"Initialised {current_app.config['DATABASE']}")


#: Inspectors and the shape of a run of visits, for `seed-demo`. The scores are
#: deliberately uneven and trend upwards: a records list where every visit scored
#: the same tells you nothing about whether the screen is doing its job.
DEMO_INSPECTORS = ("R. Anand", "Kavya Menon", "S. Prasad", "Meera Iyer")
DEMO_NOTES = (
    "Follow up on the chimney filters before the next visit.",
    "Kitchen was mid-service; recheck storage after closing.",
    "Everything raised last week has been closed out.",
    "Waste segregation still inconsistent at the back door.",
    "",
)
DEMO_COMMENTS = (
    "Two staff without hairnets at the counter.",
    "Sanitiser refilled during the visit.",
    "Rear drain still slow to clear.",
    "New labels in use since Monday.",
    "Checked with the supervisor, corrected on the spot.",
)


def seed_demo(db=None, visits=14):
    """Write a run of inspection visits, so the records screens have real data.

    Deterministic (fixed PRNG seed), so a re-seed produces the same book of
    visits and a screenshot taken from it stays true. Refuses to run against a
    database that already has records rather than doubling them up.
    """
    import random
    from datetime import date as _date, time as _time, timedelta

    db = db or get_db()
    init_db(db)

    existing = db.execute("SELECT COUNT(*) AS n FROM checklist").fetchone()[0]
    if existing:
        return 0

    rng = random.Random(20260909)
    fields = db.execute(
        "SELECT id, field_type FROM fields ORDER BY position, id"
    ).fetchall()
    today = _date.today()

    for visit in range(visits):
        # Roughly weekly, oldest first, so the list reads as a history.
        when = today - timedelta(days=(visits - 1 - visit) * 7 + rng.randint(0, 2))
        hour = rng.choice((9, 11, 14, 16))
        quality = 0.55 + 0.03 * visit + rng.uniform(-0.12, 0.12)
        cursor = db.execute(
            "INSERT INTO checklist (date, time, inspector_name, notes, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                when.isoformat(),
                _time(hour, rng.choice((0, 15, 30))).strftime("%H:%M"),
                DEMO_INSPECTORS[visit % len(DEMO_INSPECTORS)],
                rng.choice(DEMO_NOTES),
                f"{when.isoformat()}T{hour:02d}:00:00",
                f"{when.isoformat()}T{hour:02d}:00:00",
            ),
        )
        checklist_id = cursor.lastrowid

        for field in fields:
            if field["field_type"] == "checkbox":
                value = "on" if rng.random() < min(quality, 0.97) else ""
            elif field["field_type"] == "number":
                value = str(rng.choice((2, 3, 4, 5)))
            else:
                value = (when - timedelta(days=rng.randint(3, 25))).isoformat()
            # A comment on roughly one field in six: enough that the detail view
            # shows what comments look like, few enough to stay readable.
            comment = rng.choice(DEMO_COMMENTS) if rng.random() < 0.16 else ""
            db.execute(
                "INSERT INTO checklist_fields (checklist_id, field_id, value, comment)"
                " VALUES (?, ?, ?, ?)",
                (checklist_id, field["id"], value, comment),
            )

    db.commit()
    return visits


@click.command("seed-demo")
@click.option("--visits", default=14, show_default=True, help="How many visits to write.")
def seed_demo_command(visits):
    """Flask CLI: fill an empty database with a run of demo inspection visits."""
    written = seed_demo(visits=visits)
    if written:
        click.echo(f"Wrote {written} demo visits to {current_app.config['DATABASE']}")
    else:
        click.echo("Database already has records; nothing written.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_demo_command)
