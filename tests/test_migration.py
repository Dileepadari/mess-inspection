"""The first version of the app stored comments as extra rows keyed
"<field_id>_comment", checkbox values as the raw "on", and had no uniqueness on
(checklist_id, field_id). These tests pin the upgrade path for a database that
is already deployed with that shape.
"""

import os
import sqlite3
import tempfile

import pytest

from messcheck import create_app, models

OLD_SCHEMA = """
CREATE TABLE fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    field_type TEXT NOT NULL,
    category TEXT NOT NULL
);
CREATE TABLE checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT, time TEXT, inspector_name TEXT
);
CREATE TABLE checklist_fields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_id INTEGER, field_id INTEGER, value TEXT
);
"""


@pytest.fixture
def legacy_db():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    conn.executemany(
        "INSERT INTO fields (id, name, field_type, category) VALUES (?, ?, ?, ?)",
        [(1, "Hairnets worn", "checkbox", "Personal Hygiene"),
         (2, "Floors cleaned", "checkbox", "Cleaning & Sanitization"),
         (3, "Fridge temperature", "number", "Food Storage")],
    )
    conn.execute(
        "INSERT INTO checklist (id, date, time, inspector_name) VALUES (1, '2025-01-06', '10:00', 'Old Inspector')"
    )
    conn.executemany(
        "INSERT INTO checklist_fields (checklist_id, field_id, value) VALUES (?, ?, ?)",
        [
            (1, "1", "on"),                    # ticked checkbox, legacy encoding
            (1, "1_comment", "Looked fine"),   # its comment, stored as a separate row
            (1, "2_comment", "Mop the corner"),  # comment with no ticked box
            (1, "3", "4"),                     # a number answer
            (1, "1", "on"),                    # duplicate row from a second save
        ],
    )
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


def test_legacy_database_is_migrated_in_place(legacy_db):
    app = create_app({"TESTING": True, "DATABASE": legacy_db, "SECRET_KEY": "test"})

    with app.app_context():
        # Fields survive, and are not re-seeded over the top.
        names = [f["name"] for f in models.list_fields()]
        assert names.count("Hairnets worn") == 1
        assert len(names) == 3

        record = models.get_record(1)
        assert record["inspector_name"] == "Old Inspector"
        assert record["notes"] == ""

        values = models.record_values(1)
        assert values[1] == {"value": "yes", "comment": "Looked fine"}
        assert values[2]["comment"] == "Mop the corner"
        assert values[2]["value"] == ""      # never ticked
        assert values[3]["value"] == "4"

        # One row per field now, and the score reads the migrated values.
        assert models.score_for(1)[0] == 1

    # The app still serves the migrated record.
    response = app.test_client().get("/records/1")
    assert response.status_code == 200
    assert b"Old Inspector" in response.data
    assert b"Looked fine" in response.data


def test_migration_is_idempotent(legacy_db):
    create_app({"TESTING": True, "DATABASE": legacy_db, "SECRET_KEY": "test"})
    app = create_app({"TESTING": True, "DATABASE": legacy_db, "SECRET_KEY": "test"})

    with app.app_context():
        assert len(models.list_fields()) == 3
        assert models.record_values(1)[1]["comment"] == "Looked fine"


def test_empty_legacy_database_leaves_no_scratch_table(legacy_db):
    """A rename with nothing to copy back must still drop the old table."""
    conn = sqlite3.connect(legacy_db)
    conn.execute("DELETE FROM checklist_fields")
    conn.commit()
    conn.close()

    app = create_app({"TESTING": True, "DATABASE": legacy_db, "SECRET_KEY": "test"})
    with app.app_context():
        from messcheck.db import get_db
        tables = {row["name"] for row in get_db().execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    assert "checklist_fields_legacy" not in tables
    assert "checklist_fields" in tables
