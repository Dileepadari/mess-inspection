"""Managing the checklist fields that every inspection form is built from."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import models
from ..constants import FIELD_TYPES, FIELD_TYPE_VALUES

bp = Blueprint("fields", __name__, url_prefix="/fields")


def _read_form(form):
    data = {
        "name": (form.get("name") or "").strip(),
        "field_type": (form.get("type") or "checkbox").strip(),
        "category": (form.get("category") or "").strip(),
    }
    errors = []
    if not data["name"]:
        errors.append("Field name is required.")
    if data["field_type"] not in FIELD_TYPE_VALUES:
        errors.append("Pick a valid field type.")
    if not data["category"]:
        errors.append("Category is required.")
    return data, errors


@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        data, errors = _read_form(request.form)
        duplicate = any(
            f["name"].lower() == data["name"].lower()
            and f["category"].lower() == data["category"].lower()
            for f in models.list_fields()
        )
        if duplicate:
            errors.append(f"\"{data['name']}\" already exists in {data['category']}.")
        if errors:
            for message in errors:
                flash(message, "error")
        else:
            models.create_field(data["name"], data["field_type"], data["category"])
            flash(f"Added \"{data['name']}\".", "success")
            return redirect(url_for("fields.index", tab="list"))

    fields = models.list_fields()
    return render_template(
        "fields.html",
        grouped=models.group_by_category(fields),
        total=len(fields),
        categories=models.all_categories(),
        field_types=FIELD_TYPES,
        tab=request.args.get("tab", "add"),
        form=request.form if request.method == "POST" else {},
    )


@bp.route("/<int:field_id>/edit", methods=["GET", "POST"])
def edit(field_id):
    field = models.get_field(field_id)
    if field is None:
        abort(404)

    if request.method == "POST":
        data, errors = _read_form(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
        else:
            models.update_field(field_id, data["name"], data["field_type"], data["category"])
            flash(f"Updated \"{data['name']}\".", "success")
            return redirect(url_for("fields.index", tab="list"))

    return render_template(
        "field_edit.html",
        field=field,
        categories=models.all_categories(),
        field_types=FIELD_TYPES,
    )


@bp.route("/<int:field_id>/delete", methods=["POST"])
def delete(field_id):
    field = models.get_field(field_id)
    if field is None:
        abort(404)
    models.delete_field(field_id)
    flash(f"Deleted \"{field['name']}\" and its saved answers.", "success")
    return redirect(url_for("fields.index", tab="list"))


@bp.route("/<int:field_id>/move", methods=["POST"])
def move(field_id):
    direction = request.form.get("direction", "up")
    if not models.move_field(field_id, direction):
        flash("That field is already at the end of its category.", "error")
    return redirect(url_for("fields.index", tab="list"))
