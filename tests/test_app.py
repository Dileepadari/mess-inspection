"""End-to-end tests over the Flask test client.

Each test gets a fresh temporary database seeded with the default fields.
"""

import csv
import io

from messcheck import models


def submit_checklist(client, fields, inspector="Asha Rao", date="2026-08-20",
                     time="09:30", ticked=None, comments=None, notes=""):
    """Post the checklist form the way a browser would: unticked boxes absent."""
    ticked = ticked if ticked is not None else [
        f["id"] for f in fields if f["field_type"] == "checkbox"
    ]
    data = {"date": date, "time": time, "inspector_name": inspector, "notes": notes}
    for field_id in ticked:
        data[str(field_id)] = "on"
    for field_id, text in (comments or {}).items():
        data[f"{field_id}_comment"] = text
    return client.post("/checklist", data=data, follow_redirects=True)


# --------------------------------------------------------------- pages ----

def test_home_renders_with_no_records(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Weekly food safety checks" in response.data
    assert b"No records yet" in response.data


def test_static_pages_render(client):
    for path in ("/about", "/contact", "/checklist", "/records", "/fields/"):
        assert client.get(path).status_code == 200, path


def test_unknown_url_renders_404_page(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert b"could not find that page" in response.data


def test_legacy_urls_redirect(client):
    assert client.get("/add_fields").headers["Location"].endswith("/fields/")
    assert client.get("/manage_records").headers["Location"].endswith("/records")
    assert client.get("/edit_field/1").headers["Location"].endswith("/fields/1/edit")
    assert client.get("/manage_records?record_id=7").headers["Location"].endswith("/records/7")


def test_quick_start_prefills_the_checklist(client):
    response = client.post(
        "/", data={"date": "2026-09-01", "inspector_name": "Ravi"}, follow_redirects=True
    )
    assert b'value="2026-09-01"' in response.data
    assert b'value="Ravi"' in response.data


# ---------------------------------------------------------------- seed ----

def test_database_is_seeded_once(app):
    from messcheck.db import init_db

    with app.app_context():
        first = len(models.list_fields())
        init_db()
        assert len(models.list_fields()) == first
        assert first > 0


# ------------------------------------------------------------- records ----

def test_submitting_a_checklist_saves_every_answer(client, app, fields):
    checkboxes = [f["id"] for f in fields if f["field_type"] == "checkbox"]
    response = submit_checklist(
        client, fields, ticked=checkboxes[:3],
        comments={checkboxes[0]: "Spotless", checkboxes[5]: "Needs attention"},
        notes="Overall fine.",
    )
    assert response.status_code == 200
    assert b"Checklist submitted successfully." in response.data

    with app.app_context():
        record = models.list_records()[0]
        assert record["inspector_name"] == "Asha Rao"
        assert record["notes"] == "Overall fine."
        values = models.record_values(record["id"])
        assert values[checkboxes[0]]["value"] == "yes"
        assert values[checkboxes[0]]["comment"] == "Spotless"
        # An unticked box is stored as "no" rather than left missing.
        assert values[checkboxes[5]]["value"] == "no"
        assert values[checkboxes[5]]["comment"] == "Needs attention"
        assert models.score_for(record["id"])[0] == 3


def test_checklist_rejects_a_missing_inspector_name(client, fields):
    response = client.post(
        "/checklist", data={"date": "2026-08-20", "time": "09:30", "inspector_name": ""}
    )
    assert response.status_code == 400
    assert b"Inspector name is required." in response.data


def test_checklist_rejects_a_bad_date(client, fields):
    response = client.post(
        "/checklist",
        data={"date": "not-a-date", "time": "09:30", "inspector_name": "Asha"},
    )
    assert response.status_code == 400
    assert b"Pick a valid inspection date." in response.data


def test_editing_a_record_can_untick_a_box(client, app, fields):
    checkboxes = [f["id"] for f in fields if f["field_type"] == "checkbox"]
    submit_checklist(client, fields, ticked=checkboxes)

    with app.app_context():
        record_id = models.list_records()[0]["id"]
        assert models.score_for(record_id)[2] == 100

    client.post(
        f"/records/{record_id}",
        data={
            "update": "1", "date": "2026-08-21", "time": "10:15",
            "inspector_name": "Asha Rao", "notes": "Re-checked",
            # Only the first box stays ticked.
            str(checkboxes[0]): "on",
        },
        follow_redirects=True,
    )

    with app.app_context():
        record = models.get_record(record_id)
        assert record["date"] == "2026-08-21"
        assert record["notes"] == "Re-checked"
        assert models.score_for(record_id)[0] == 1
        values = models.record_values(record_id)
        assert values[checkboxes[1]]["value"] == "no"


def test_editing_a_record_never_duplicates_answer_rows(client, app, fields):
    """The original app used REPLACE INTO without a unique key, so every save
    appended a fresh row. Saving twice must still leave one row per field."""
    checkboxes = [f["id"] for f in fields if f["field_type"] == "checkbox"]
    submit_checklist(client, fields, ticked=checkboxes[:2])

    with app.app_context():
        record_id = models.list_records()[0]["id"]

    for _ in range(3):
        client.post(
            f"/records/{record_id}",
            data={"update": "1", "date": "2026-08-20", "time": "09:30",
                  "inspector_name": "Asha Rao", str(checkboxes[0]): "on"},
            follow_redirects=True,
        )

    with app.app_context():
        from messcheck.db import query
        rows = query(
            "SELECT field_id, COUNT(*) AS n FROM checklist_fields"
            " WHERE checklist_id = ? GROUP BY field_id", (record_id,)
        )
        assert all(row["n"] == 1 for row in rows)


def test_delete_requires_the_matching_inspector_name(client, app, fields):
    submit_checklist(client, fields)
    with app.app_context():
        record_id = models.list_records()[0]["id"]

    wrong = client.post(
        f"/records/{record_id}",
        data={"delete": "1", "inspector_name_confirm": "Someone Else"},
        follow_redirects=True,
    )
    assert b"does not match the inspector" in wrong.data
    with app.app_context():
        assert models.get_record(record_id) is not None

    right = client.post(
        f"/records/{record_id}",
        data={"delete": "1", "inspector_name_confirm": "asha rao"},  # case-insensitive
        follow_redirects=True,
    )
    assert b"deleted" in right.data
    with app.app_context():
        assert models.get_record(record_id) is None
        from messcheck.db import query
        assert query(
            "SELECT * FROM checklist_fields WHERE checklist_id = ?", (record_id,)
        ) == []


def test_missing_record_returns_404(client):
    assert client.get("/records/9999").status_code == 404


def test_records_can_be_filtered(client, fields):
    submit_checklist(client, fields, inspector="Asha Rao", date="2026-08-01")
    submit_checklist(client, fields, inspector="Bimal Sen", date="2026-08-20")

    assert b"Bimal Sen" not in client.get("/records?q=Asha").data
    assert b"Asha Rao" not in client.get("/records?q=Bimal").data
    ranged = client.get("/records?from=2026-08-10&to=2026-08-31").data
    assert b"Bimal Sen" in ranged and b"Asha Rao" not in ranged
    assert b"No matches" in client.get("/records?q=nobody").data


# ------------------------------------------------------------- exports ----

def test_single_record_csv_export(client, app, fields):
    checkboxes = [f["id"] for f in fields if f["field_type"] == "checkbox"]
    submit_checklist(client, fields, ticked=checkboxes[:1],
                     comments={checkboxes[0]: "All good"})
    with app.app_context():
        record_id = models.list_records()[0]["id"]

    response = client.get(f"/records/{record_id}/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    body = response.get_data(as_text=True)
    assert "Asha Rao" in body and "All good" in body
    assert "Verified" in body and "Not verified" in body


def test_all_records_csv_export_respects_filters(client, fields):
    submit_checklist(client, fields, inspector="Asha Rao", date="2026-08-01")
    submit_checklist(client, fields, inspector="Bimal Sen", date="2026-08-20")

    rows = list(csv.reader(io.StringIO(
        client.get("/records/export?q=Asha").get_data(as_text=True)
    )))
    assert len(rows) == 2  # header + one match
    assert rows[1][3] == "Asha Rao"


# -------------------------------------------------------------- fields ----

def test_adding_a_field(client, app):
    response = client.post(
        "/fields/",
        data={"name": "Water filter serviced", "type": "checkbox", "category": "Equipment Maintenance"},
        follow_redirects=True,
    )
    assert b"Added &#34;Water filter serviced&#34;" in response.data \
        or b'Added "Water filter serviced"' in response.data
    with app.app_context():
        assert any(f["name"] == "Water filter serviced" for f in models.list_fields())


def test_adding_a_duplicate_field_is_refused(client):
    data = {"name": "Ice machine cleaned", "type": "checkbox", "category": "Equipment Maintenance"}
    client.post("/fields/", data=data, follow_redirects=True)
    response = client.post("/fields/", data=data, follow_redirects=True)
    assert b"already exists in Equipment Maintenance" in response.data


def test_adding_a_field_without_a_name_is_refused(client, app):
    with app.app_context():
        before = len(models.list_fields())
    response = client.post(
        "/fields/", data={"name": "  ", "type": "checkbox", "category": "Pest Control"},
        follow_redirects=True,
    )
    assert b"Field name is required." in response.data
    with app.app_context():
        assert len(models.list_fields()) == before


def test_adding_a_field_with_an_unknown_type_is_refused(client):
    response = client.post(
        "/fields/", data={"name": "Odd", "type": "rocket", "category": "Pest Control"},
        follow_redirects=True,
    )
    assert b"Pick a valid field type." in response.data


def test_a_new_category_is_accepted_and_grouped(client, app):
    client.post(
        "/fields/", data={"name": "Water tank chlorinated", "type": "checkbox",
                          "category": "Water Safety"},
        follow_redirects=True,
    )
    response = client.get("/checklist")
    assert b"Water Safety" in response.data
    with app.app_context():
        assert "Water Safety" in models.all_categories()


def test_editing_a_field_keeps_its_answers(client, app, fields):
    checkboxes = [f["id"] for f in fields if f["field_type"] == "checkbox"]
    submit_checklist(client, fields, ticked=checkboxes[:2])
    with app.app_context():
        record_id = models.list_records()[0]["id"]

    target = checkboxes[0]
    client.post(
        f"/fields/{target}/edit",
        data={"name": "Renamed check", "type": "checkbox", "category": "Personal Hygiene"},
        follow_redirects=True,
    )
    with app.app_context():
        assert models.get_field(target)["name"] == "Renamed check"
        assert models.record_values(record_id)[target]["value"] == "yes"


def test_edit_page_preselects_the_current_category(client, fields):
    """The original template read the category from the wrong column index, so
    the dropdown always fell back to the first option."""
    field = next(f for f in fields if f["category"] == "Pest Control")
    body = client.get(f"/fields/{field['id']}/edit").get_data(as_text=True)
    assert 'value="Pest Control"' in body


def test_deleting_a_field_removes_its_answers(client, app, fields):
    checkboxes = [f["id"] for f in fields if f["field_type"] == "checkbox"]
    submit_checklist(client, fields, ticked=checkboxes[:2])
    with app.app_context():
        record_id = models.list_records()[0]["id"]

    target = checkboxes[0]
    response = client.post(f"/fields/{target}/delete", follow_redirects=True)
    assert b"Deleted" in response.data
    with app.app_context():
        assert models.get_field(target) is None
        assert target not in models.record_values(record_id)


def test_deleting_a_field_needs_a_post(client, fields):
    assert client.get(f"/fields/{fields[0]['id']}/delete").status_code == 405


def test_deleting_a_missing_field_returns_404(client):
    assert client.post("/fields/9999/delete").status_code == 404


def test_moving_a_field_reorders_within_its_category(client, app):
    with app.app_context():
        hygiene = [f["id"] for f in models.list_fields()
                   if f["category"] == "Personal Hygiene"]

    client.post(f"/fields/{hygiene[1]}/move", data={"direction": "up"}, follow_redirects=True)
    with app.app_context():
        reordered = [f["id"] for f in models.list_fields()
                     if f["category"] == "Personal Hygiene"]
    assert reordered[0] == hygiene[1] and reordered[1] == hygiene[0]


def test_moving_the_first_field_up_is_reported(client, app):
    with app.app_context():
        first = [f["id"] for f in models.list_fields()
                 if f["category"] == "Personal Hygiene"][0]
    response = client.post(f"/fields/{first}/move", data={"direction": "up"},
                           follow_redirects=True)
    assert b"already at the end of its category" in response.data


# ------------------------------------------------------------- scoring ----

def test_score_ignores_non_checkbox_fields(client, app, fields):
    checkboxes = [f["id"] for f in fields if f["field_type"] == "checkbox"]
    number_field = next(f["id"] for f in fields if f["field_type"] == "number")
    data = {"date": "2026-08-20", "time": "09:30", "inspector_name": "Asha Rao",
            str(number_field): "4"}
    for field_id in checkboxes:
        data[str(field_id)] = "on"
    client.post("/checklist", data=data, follow_redirects=True)

    with app.app_context():
        record_id = models.list_records()[0]["id"]
        checked, total, percent = models.score_for(record_id)
        assert total == len(checkboxes)
        assert percent == 100
        assert models.record_values(record_id)[number_field]["value"] == "4"
