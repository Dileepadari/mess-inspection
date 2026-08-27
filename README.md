<p align="center">
  <img src="./messcheck/static/logo-mark.png" width="96" alt="ADK DEV">
</p>

# MessCheck

A food safety inspection checklist for the IIITH mess. An inspector opens the form, ticks
what they verified, comments on what needs follow-up, and the visit is saved as a record
with a compliance score.

It replaces a paper form that circulated between inspectors, so every visit is in one place
and can be compared with the previous one.

For architecture, data model, and setup, see **[DEVDOC.md](./DEVDOC.md)**.

## Features

### Running a check
- Start from the home page by entering a date and your name, or open the blank form directly
- Fields are grouped into collapsible categories so a long checklist stays manageable
- Every field carries a comment box, whatever its type, for context that does not fit a tick
- A progress bar counts verified items as you work down the form
- The form validates the date, time and inspector name before saving, and hands back what
  you typed if something is wrong

### Records
- Every record shows a compliance score: the share of checkbox items that were verified
- Scores are colour coded - green at 80% and above, amber from 50%, red below
- Search by inspector name and filter by date range
- Each record has three tabs: view the answers, edit them, or delete the record
- Editing can untick a box, and the change sticks
- Deleting asks you to retype the inspector's name, and the button stays disabled until it
  matches
- Export one record, or the whole filtered list, as CSV

### Managing the checklist
- Add, rename, retype, reorder and delete the fields the form is built from
- Three field types: checkbox (scored), short text and number (recorded, not scored)
- Categories group the form into sections; typing a category that does not exist creates it
- Deleting a field also removes the answers recorded against it, and says so first
- Renaming or moving a field leaves existing answers untouched

### Interface
- Works on a phone: the nav becomes a drawer and record tables stack into labelled cards
- Light and dark themes, following the system setting until you pick one
- Records print cleanly - navigation, tabs and buttons drop out, and all tabs expand

## Roles

There are no accounts. Anyone who can reach the site can record a check, edit a record, or
change the field list, so it is meant for an internal network or a trusted group. See
[DEVDOC.md](./DEVDOC.md#known-constraints-and-gotchas) before putting it on the open web.

## The record lifecycle

1. **Draft** - the form is open in the browser. Nothing is stored yet.
2. **Saved** - submitting writes the record header (date, time, inspector, notes) and one row
   per answered field. The score is computed from the checkbox answers.
3. **Amended** - editing rewrites every answer for that record, so unticking a box or clearing
   a comment removes it rather than leaving the old value behind.
4. **Deleted** - a confirmed delete removes the record and its answers together.

A record keeps the fields it was answered against. Adding a new field does not retroactively
mark old records as failing it - the field simply has no answer there.

## Tech stack

Flask 3 and SQLite, server-rendered Jinja templates, no build step and no front-end
framework. Detail in [DEVDOC.md](./DEVDOC.md).

## Getting started

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open http://127.0.0.1:5000. The database is created and seeded with a default checklist
on first run. Full setup and deployment notes are in [DEVDOC.md](./DEVDOC.md#local-development).
