"""Home, about and contact pages."""

from datetime import datetime

from flask import Blueprint, redirect, render_template, request, url_for

from .. import models

bp = Blueprint("pages", __name__)


@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # The quick-start form only pre-fills the checklist; nothing is saved
        # until the checklist itself is submitted.
        return redirect(
            url_for(
                "records.new",
                date=request.form.get("date", ""),
                inspector_name=request.form.get("inspector_name", "").strip(),
            )
        )

    return render_template(
        "index.html",
        stats=models.dashboard_stats(),
        records=models.recent_records(5),
        scores=models.scores_for_records(models.recent_records(5)),
        today=datetime.now().strftime("%Y-%m-%d"),
    )


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/contact")
def contact():
    return render_template("contact.html")


# Backwards-compatible URLs from the first version of the app, so existing
# bookmarks and the deployed site's links keep working.
@bp.route("/add_fields")
def legacy_add_fields():
    return redirect(url_for("fields.index"))


@bp.route("/edit_field/<int:field_id>")
def legacy_edit_field(field_id):
    return redirect(url_for("fields.edit", field_id=field_id))
