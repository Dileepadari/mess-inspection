# MessCheck - Developer Documentation

Technical reference for the MessCheck codebase: architecture, data model, route surface,
and setup/deployment. For what the app does from a user's point of view, see
[README.md](./README.md).

## Table of contents

- [Tech stack](#tech-stack)
- [Architecture overview](#architecture-overview)
- [Project structure](#project-structure)
- [Route surface](#route-surface)
- [Data model](#data-model)
- [Answer encoding and scoring](#answer-encoding-and-scoring)
- [Schema migration](#schema-migration)
- [Theming](#theming)
- [Front-end behaviour](#front-end-behaviour)
- [Testing](#testing)
- [Environment variables](#environment-variables)
- [Local development](#local-development)
- [Deployment](#deployment)
- [Known constraints and gotchas](#known-constraints-and-gotchas)

## Tech stack

Python 3.12, Flask 3, SQLite through the standard library `sqlite3` module. Templates are
server-rendered Jinja2. There is no build step, no bundler, and no front-end framework: one
hand-written stylesheet and one plain-JS file, both served from `messcheck/static/`. Inter is
pulled from Google Fonts with a system-font fallback stack, so the app still renders correctly
offline. pytest drives the tests through Flask's test client.

There is no auth layer and no ORM. Both are deliberate for an internal, single-table-ish tool;
see [gotchas](#known-constraints-and-gotchas) for what that costs.

## Architecture overview

```
  browser
     |  form posts, GET navigations
     v
  Flask app  (messcheck/__init__.py: create_app)
     |
     +-- views/pages.py       home, about, contact, legacy redirects
     +-- views/records.py     checklist form, record list/detail/edit/delete, CSV export
     +-- views/fields.py      field CRUD and reordering
     |
     v
  models.py    data access + scoring, returns sqlite3.Row
     |
     v
  db.py        request-scoped connection on flask.g, schema, migration, seeding
     |
     v
  checklist.db (SQLite file)
```

`create_app` is an application factory: it reads config, registers the three blueprints,
installs template filters and error handlers, and runs `init_db()` once inside an app context
so a fresh checkout has a working database without a manual step.

Views own request parsing, validation, flashing and redirects. `models.py` owns SQL and
domain rules (scoring, grouping, ordering) and never touches `request`. `db.py` owns the
connection lifecycle and nothing above it.

## Project structure

```
app.py                    dev-server entry point; also exposes `app` for WSGI hosts
wsgi.py                   production WSGI entry point (`application`)
messcheck/
  __init__.py             application factory, template filters, error handlers
  constants.py            app name, field types, default categories, seed checklist
  db.py                   connection handling, schema, migration, seeding, `init-db` CLI
  models.py               all SQL plus scoring, grouping and stats helpers
  views/
    pages.py              home (with quick-start), about, contact, legacy URL redirects
    records.py            new check, record list, record detail/update/delete, CSV export
    fields.py             field add/edit/delete/move
  templates/
    base.html             shell: head, header/nav, flash area, content block, footer
    _macros.html          score badge, meter, empty state, the shared records table
    index.html            home: hero + quick start, stat tiles, recent records
    checklist.html        the inspection form
    records.html          filterable record list
    record_detail.html    view / edit / delete tabs for one record
    fields.html           add-field form and the grouped field list
    field_edit.html       single field edit form
    about.html contact.html error.html
  static/
    styles.css            design tokens, components, responsive and print rules
    app.js                nav drawer, theme toggle, tabs, collapsibles, delete gate, progress
    logo-mark.png         ADK DEV mark: favicon and header badge
tests/
  conftest.py             app/client fixtures on a temporary database
  test_app.py             route and CRUD coverage through the test client
  test_migration.py       upgrade path from the original schema
```

## Route surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Dashboard: stats, recent records, quick-start form |
| POST | `/` | Quick start - redirects to `/checklist` with date and name prefilled |
| GET | `/checklist` | Blank inspection form. Accepts `?date=` and `?inspector_name=` |
| POST | `/checklist` | Create a record. Re-renders with errors and HTTP 400 if invalid |
| GET | `/records` | Record list. Filters: `?q=` inspector, `?from=`, `?to=` (ISO dates) |
| GET | `/records/<id>` | Record detail. `?tab=view\|edit\|delete` selects the open tab |
| POST | `/records/<id>` | `update` in the body saves edits; `delete` deletes after the name check |
| GET | `/records/<id>/export` | One record as CSV |
| GET | `/records/export` | All records as CSV, honouring the same filters as the list |
| GET | `/fields/` | Field manager. `?tab=add\|list` |
| POST | `/fields/` | Create a field |
| GET/POST | `/fields/<id>/edit` | Edit a field |
| POST | `/fields/<id>/delete` | Delete a field and its answers. POST only - a GET returns 405 |
| POST | `/fields/<id>/move` | Swap a field with its neighbour. Body: `direction=up\|down` |
| GET | `/about`, `/contact` | Static pages |

Legacy URLs from the first version still resolve, so existing bookmarks and the deployed
site's links keep working:

| Old | Redirects to |
|---|---|
| `/manage_records?record_id=N` | `/records/N` (bare `/manage_records` goes to `/records`) |
| `/add_fields` | `/fields/` |
| `/edit_field/N` | `/fields/N/edit` |

## Data model

Dates are stored as ISO `YYYY-MM-DD` strings and times as `HH:MM`, both in the server's local
timezone with no offset recorded. Sorting relies on the ISO ordering being lexicographic.
`created_at` / `updated_at` are local ISO-8601 timestamps to the second.

**fields** - the questions every inspection form is built from.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `name` | TEXT NOT NULL | Shown on the form |
| `field_type` | TEXT NOT NULL | `checkbox`, `text` or `number`; validated in the view |
| `category` | TEXT NOT NULL | Free text. Known values are ordered first when grouping |
| `position` | INTEGER NOT NULL | Sort order *within* a category |
| `created_at` | TEXT NOT NULL | |

**checklist** - one row per inspection. The table keeps its original name so existing
deployments migrate in place.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `date` | TEXT NOT NULL | ISO date |
| `time` | TEXT NOT NULL | `HH:MM` |
| `inspector_name` | TEXT NOT NULL | Also the delete confirmation phrase |
| `notes` | TEXT NOT NULL | Free text, defaults to empty |
| `created_at`, `updated_at` | TEXT NOT NULL | |

**checklist_fields** - one row per answered field per inspection.

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | |
| `checklist_id` | INTEGER NOT NULL | FK to `checklist(id)` ON DELETE CASCADE |
| `field_id` | INTEGER NOT NULL | FK to `fields(id)` ON DELETE CASCADE |
| `value` | TEXT NOT NULL | See [answer encoding](#answer-encoding-and-scoring) |
| `comment` | TEXT NOT NULL | Defaults to empty |

`UNIQUE (checklist_id, field_id)` is the constraint that matters: it is what makes an answer
row per field per record a real invariant rather than a hope. Indexes: `checklist(date DESC)`
and `checklist_fields(checklist_id)`.

The foreign keys declare `ON DELETE CASCADE` and `PRAGMA foreign_keys = ON` is set per
connection, but deletes in `models.py` still remove child rows explicitly, so behaviour does
not depend on the pragma surviving a connection change.

## Answer encoding and scoring

A checkbox answer is stored as the literal string `yes` or `no`. Storing `no` explicitly is
the point: browsers omit unticked checkboxes from a form post entirely, so a save that only
wrote what arrived could never turn a box back off. `models.parse_answers` walks the field
list rather than the submitted keys, and `_save_answers` deletes the record's answers before
reinserting, so an edit is a full replacement.

`models.TRUTHY` accepts `yes`, `on`, `1` and `true` when reading, because rows migrated from
the original schema contain `on`.

`text` and `number` answers are stored as the raw submitted string. `number` is not cast;
SQLite would accept it either way and the value is only ever displayed or exported.

Scoring (`models.score_for`) counts ticked checkboxes over total checkbox fields and returns
`(checked, total, percent)`. `percent` is `None` when there are no checkbox fields at all.
Text and number fields are excluded deliberately - there is no single correct answer to count.
The score is computed on read, never stored, so it always reflects the current field list.

## Schema migration

`db._migrate` runs before `executescript(SCHEMA)` on every start and upgrades a database
written by the original version. That version:

- stored a comment as a *separate row* whose `field_id` was the string `"<id>_comment"`
- stored a ticked checkbox as the raw HTML value `"on"`
- had no `UNIQUE (checklist_id, field_id)`, and used `REPLACE INTO`, which without a unique
  key is a plain insert - so every re-save appended another row

The migration renames `checklist_fields` aside, folds the `_comment` rows into the new
`comment` column, normalises `"on"` to `"yes"`, deduplicates by `(checklist_id, field_id)`,
recreates the table from the current schema, copies the rows back and drops the old table. It
also adds the columns later versions added to `fields` and `checklist`. It is idempotent, and
`tests/test_migration.py` pins both the upgrade and the re-run.

Seeding only happens when `fields` is empty, so a migrated database keeps its own questions
and a fresh one gets the 18 defaults from `constants.SEED_FIELDS`.

## Theming

The palette is a set of CSS custom properties at the top of `messcheck/static/styles.css`.
Light values live on bare `:root`. Dark values are declared twice: once under
`@media (prefers-color-scheme: dark)` guarded as `:root:not([data-theme="light"])`, and once
under `:root[data-theme="dark"]` so an explicit choice wins in both directions.

Three states, in effect: no `data-theme` attribute means follow the system; `data-theme="light"`
and `data-theme="dark"` are explicit. The choice is stored in `localStorage` under
`messcheck-theme` and applied by an inline script in `<head>`, before first paint, so the page
never flashes the wrong theme. Every `localStorage` access is wrapped in try/catch - it throws
outright in some privacy modes.

The brand colour `--brand: #47266B` is the ADK DEV purple. The logo mark is a solid purple PNG
on transparent, and would vanish on the dark header, so `.logo-mono` applies
`filter: brightness(0) invert(1)` to flatten it to white while keeping its alpha shape. There
is no second recoloured file.

Date and time inputs get `color-scheme: dark` in dark mode; without it Chrome renders the
native picker glyphs dark-on-dark.

## Front-end behaviour

`app.js` is one IIFE, no dependencies, and every block is defensive about its elements being
absent - the same file loads on every page.

- **Nav drawer** - below 780px the nav becomes a fixed right-hand drawer. The toggle keeps
  `aria-expanded` in sync, a backdrop closes it, Escape closes it, and a resize past the
  breakpoint resets it (otherwise a drawer opened on a phone stays stuck open on rotation).
- **Tabs** - `[data-tabs]` marks a group; its value is the initially selected tab, which the
  server sets from `?tab=`. Clicking updates `aria-selected`, toggles the panels' `hidden`,
  and `replaceState`s `?tab=` so a reload or a flash redirect lands back on the same tab.
  Left/right arrows move between tabs.
- **Collapsible categories** - `.category-head` toggles `aria-expanded` and its panel's
  `hidden`. Inputs inside a collapsed panel still submit; `hidden` does not disable them.
- **Delete gate** - `[data-confirm-name]` keeps the submit button disabled until the typed
  name matches, case-insensitively. This is a convenience, not the check: `records.detail`
  re-validates server-side and the tests cover the server path.
- **Progress meter** - counts ticked boxes on the checklist form and recolours the bar.

## Testing

```bash
.venv/bin/python -m pytest tests -q
```

32 tests, all through Flask's test client against a temporary SQLite file per test, so they
never touch the working database. `tests/test_app.py` covers page rendering, the create /
edit / delete flows, filtering, CSV export, field CRUD and reordering, and scoring.
`tests/test_migration.py` builds a database in the original schema and asserts the upgrade.

Several tests exist specifically to pin bugs the refactor fixed, and are worth keeping
recognisable: unticking a box on edit, no duplicate answer rows after repeated saves, the
delete name check, the edit page preselecting the right category, and field deletion removing
its answers.

Not covered: the JavaScript (no browser harness), and concurrent writes.

## Environment variables

All are server-side. There is no client bundle, so nothing is exposed to the browser.

| Variable | Default | Purpose |
|---|---|---|
| `MESSCHECK_SECRET_KEY` | `dev-only-change-me` | Flask session key, signs the flash cookie. Set a real value in production |
| `MESSCHECK_DB` | `<repo root>/checklist.db` | Absolute path to the SQLite file |
| `FLASK_DEBUG` | `1` | `app.py` only. `0` disables the debugger and the reloader |
| `HOST` | `127.0.0.1` | `app.py` only |
| `PORT` | `5000` | `app.py` only |

`checklist.db` is gitignored. Do not commit it - it was tracked in the first version and has
been removed from the index.

## Local development

```bash
git clone <repo> && cd MessCheck
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Open http://127.0.0.1:5000. The database is created and seeded on first start.

To create or upgrade the database without starting a server:

```bash
.venv/bin/flask --app app init-db
```

Run the tests with `.venv/bin/python -m pytest tests -q`.

Templates are only auto-reloaded when debug is on. `FLASK_DEBUG=0` caches them, so a template
edit will not appear until you restart - this costs time if you forget.

## Deployment

The app is a plain WSGI application; `wsgi.py` exposes `application`.

**PythonAnywhere** (where this has been hosted): point the web app's WSGI file at
`wsgi.application`, set the source directory to the repo, add `MESSCHECK_SECRET_KEY` and an
absolute `MESSCHECK_DB` under a writable path, install `requirements.txt` into the virtualenv,
and reload. The migration runs automatically on the first request after deploy, so an existing
`checklist.db` upgrades in place - **back the file up first**, since the migration rewrites
`checklist_fields`.

**gunicorn**: `gunicorn wsgi:application`.

Do not run `app.py` in production; it starts Flask's development server.

## Known constraints and gotchas

- **No authentication.** Every route is open, including delete. Put it behind a network
  boundary, a reverse-proxy basic-auth, or add auth before exposing it publicly.
- **No CSRF protection.** State-changing routes are plain form posts with no token. That is
  survivable behind a trusted boundary and not otherwise. Adding Flask-WTF would be the fix.
- **`SECRET_KEY` defaults to a known string.** Flashes are the only thing signed with it
  today, but set `MESSCHECK_SECRET_KEY` anyway - anything session-based added later inherits
  this.
- **SQLite writer lock.** Concurrent submissions from several inspectors at once can raise
  "database is locked". Fine for a weekly check by one person; not a general-purpose setup.
- **Deleting a field destroys history.** The answers recorded against it in past inspections
  go too, which changes those records' scores. The UI warns; there is no undo. Renaming is
  almost always what is wanted instead.
- **Scores are relative to the current field list.** Adding a checkbox field lowers the
  denominator-relative score of every past record that has no answer for it, since an absent
  answer counts as unverified. This is intentional - it keeps "score" meaning "share of the
  current checklist verified" - but it does mean historical scores can move.
- **Local timezone, unrecorded.** Dates and times come from the server's clock with no offset
  stored. Moving the host between timezones shifts what new records mean relative to old ones.
- **Template caching with debug off.** See [local development](#local-development).
- **The `time` column is `HH:MM`.** A migrated database may hold `HH:MM:SS`; the
  `pretty_time` filter accepts both, and `_read_form` truncates input to five characters.
