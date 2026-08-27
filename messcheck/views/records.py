"""Creating, listing, editing, deleting and exporting inspection records."""

import csv
import io
from datetime import datetime

from flask import (
    Blueprint, Response, abort, flash, redirect, render_template, request, url_for
)

from .. import models

bp = Blueprint("records", __name__)


def _valid_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def _valid_time(value):
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            datetime.strptime(value, fmt)
            return True
        except (ValueError, TypeError):
            continue
    return False


def _read_form(form):
    """Pull the record header out of a submitted form and validate it."""
    data = {
        "date": (form.get("date") or "").strip(),
        "time": (form.get("time") or "").strip()[:5],
        "inspector_name": (form.get("inspector_name") or "").strip(),
        "notes": (form.get("notes") or "").strip(),
    }
    errors = []
    if not data["inspector_name"]:
        errors.append("Inspector name is required.")
    elif len(data["inspector_name"]) < 2:
        errors.append("Inspector name looks too short.")
    if not _valid_date(data["date"]):
        errors.append("Pick a valid inspection date.")
    if not _valid_time(data["time"]):
        errors.append("Pick a valid inspection time.")
    return data, errors


@bp.route("/checklist", methods=["GET", "POST"])
def new():
    fields = models.list_fields()
    now = datetime.now()

    if request.method == "POST":
        data, errors = _read_form(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "checklist.html",
                categories=models.group_by_category(fields),
                form=request.form,
                values=models.parse_answers(request.form, fields),
                record=None,
                date=data["date"] or now.strftime("%Y-%m-%d"),
                time=data["time"] or now.strftime("%H:%M"),
                inspector_name=data["inspector_name"],
                notes=data["notes"],
            ), 400

        record_id = models.create_record(
            data["date"], data["time"], data["inspector_name"], data["notes"],
            models.parse_answers(request.form, fields),
        )
        flash("Checklist submitted successfully.", "success")
        return redirect(url_for("records.detail", record_id=record_id))

    return render_template(
        "checklist.html",
        categories=models.group_by_category(fields),
        values={},
        record=None,
        date=request.args.get("date") or now.strftime("%Y-%m-%d"),
        time=now.strftime("%H:%M"),
        inspector_name=request.args.get("inspector_name", ""),
        notes="",
    )


@bp.route("/records")
def index():
    search = request.args.get("q", "").strip()
    date_from = request.args.get("from", "").strip()
    date_to = request.args.get("to", "").strip()
    records = models.list_records(search, date_from, date_to)
    fields = models.list_fields()
    return render_template(
        "records.html",
        records=records,
        scores=models.scores_for_records(records, fields),
        search=search,
        date_from=date_from,
        date_to=date_to,
        filtered=bool(search or date_from or date_to),
    )


@bp.route("/records/<int:record_id>", methods=["GET", "POST"])
def detail(record_id):
    record = models.get_record(record_id)
    if record is None:
        abort(404)
    fields = models.list_fields()

    if request.method == "POST":
        if "delete" in request.form:
            confirm = (request.form.get("inspector_name_confirm") or "").strip()
            if confirm.lower() != record["inspector_name"].strip().lower():
                flash(
                    "The name you typed does not match the inspector on this record.",
                    "error",
                )
                return redirect(url_for("records.detail", record_id=record_id, tab="delete"))
            models.delete_record(record_id)
            flash(f"Record #{record_id} deleted.", "success")
            return redirect(url_for("records.index"))

        data, errors = _read_form(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("records.detail", record_id=record_id, tab="edit"))

        models.update_record(
            record_id, data["date"], data["time"], data["inspector_name"],
            data["notes"], models.parse_answers(request.form, fields),
        )
        flash("Record updated.", "success")
        return redirect(url_for("records.detail", record_id=record_id))

    checked, total, percent = models.score_for(record_id, fields)
    return render_template(
        "record_detail.html",
        record=record,
        categories=models.group_by_category(fields),
        values=models.record_values(record_id),
        checked=checked,
        total=total,
        percent=percent,
        tab=request.args.get("tab", "view"),
    )


@bp.route("/records/<int:record_id>/export")
def export_one(record_id):
    record = models.get_record(record_id)
    if record is None:
        abort(404)
    fields = models.list_fields()
    values = models.record_values(record_id)

    rows = [["Category", "Field", "Type", "Value", "Comment"]]
    for field in fields:
        entry = values.get(field["id"], {})
        rows.append([
            field["category"], field["name"], field["field_type"],
            _display_value(field, entry.get("value")), entry.get("comment", ""),
        ])

    header = [
        ["Record", record["id"]],
        ["Date", record["date"]],
        ["Time", record["time"]],
        ["Inspector", record["inspector_name"]],
        ["Notes", record["notes"]],
        [],
    ]
    filename = f"messcheck-record-{record['id']}-{record['date']}.csv"
    return _csv_response(header + rows, filename)


@bp.route("/records/export")
def export_all():
    records = models.list_records(
        request.args.get("q", "").strip(),
        request.args.get("from", "").strip(),
        request.args.get("to", "").strip(),
    )
    fields = models.list_fields()

    rows = [["ID", "Date", "Time", "Inspector", "Score %", "Notes"]
            + [f["name"] for f in fields]]
    for record in records:
        values = models.record_values(record["id"])
        percent = models.score_for(record["id"], fields)[2]
        rows.append(
            [record["id"], record["date"], record["time"], record["inspector_name"],
             "" if percent is None else percent, record["notes"]]
            + [_display_value(f, values.get(f["id"], {}).get("value")) for f in fields]
        )
    stamp = datetime.now().strftime("%Y%m%d")
    return _csv_response(rows, f"messcheck-records-{stamp}.csv")


def _display_value(field, value):
    if field["field_type"] != "checkbox":
        return value or ""
    return "Verified" if (value or "").lower() in models.TRUTHY else "Not verified"


def _csv_response(rows, filename):
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Backwards-compatible routes from the first version of the app.
@bp.route("/manage_records")
def legacy_manage():
    record_id = request.args.get("record_id", type=int)
    if record_id is None:
        return redirect(url_for("records.index"))
    return redirect(url_for("records.detail", record_id=record_id))
