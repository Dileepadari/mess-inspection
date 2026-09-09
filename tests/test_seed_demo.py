"""The demo seeder: real records for the screens that list and compare them."""

from __future__ import annotations

from messcheck.db import seed_demo


def test_writes_a_run_of_visits_with_answers(app):
    with app.app_context():
        written = seed_demo(visits=5)

        from messcheck.db import get_db

        db = get_db()
        assert written == 5
        assert db.execute("SELECT COUNT(*) AS n FROM checklist").fetchone()[0] == 5
        # Every visit answers every field, or the compliance score on the records
        # list is computed against a different denominator per row.
        fields = db.execute("SELECT COUNT(*) AS n FROM fields").fetchone()[0]
        answers = db.execute("SELECT COUNT(*) AS n FROM checklist_fields").fetchone()[0]
        assert answers == fields * 5


def test_is_deterministic(app):
    with app.app_context():
        seed_demo(visits=4)
        from messcheck.db import get_db

        first = [tuple(row) for row in get_db().execute(
            "SELECT date, inspector_name, notes FROM checklist ORDER BY id"
        )]

    with app.app_context():
        get_db_second = __import__("messcheck.db", fromlist=["get_db"]).get_db
        get_db_second().execute("DELETE FROM checklist")
        get_db_second().commit()
        seed_demo(visits=4)
        second = [tuple(row) for row in get_db_second().execute(
            "SELECT date, inspector_name, notes FROM checklist ORDER BY id"
        )]

    assert first == second


def test_refuses_to_double_up(app):
    with app.app_context():
        seed_demo(visits=3)
        assert seed_demo(visits=3) == 0

        from messcheck.db import get_db

        assert get_db().execute("SELECT COUNT(*) AS n FROM checklist").fetchone()[0] == 3
