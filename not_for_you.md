# not_for_you.md

A personal working log. Not documentation, and nothing here is needed to use or
contribute to MessCheck. Everything a newcomer actually needs is in
[README.md](./README.md) and [DEVDOC.md](./DEVDOC.md).

---

## A fresh install shows nothing

The database seeds 18 checklist fields on first run, and no records. Which is
correct: nobody has done an inspection yet. It also means Records is an empty
table, a record's detail page cannot be reached at all, and three of the four
tiles on the home page read zero.

So `flask --app app seed-demo` now writes a run of visits. The generator lives in
`messcheck/db.py` beside the schema it writes against, and three details in it are
deliberate:

- **Scores are uneven and trend upward** across the run. A records list where
  every visit scored the same proves nothing about the colour coding or the
  sorting, and the whole point of the screen is comparing one visit with the one
  before.
- **Comments land on about one field in six.** Enough that the detail page shows
  what a comment looks like sitting next to a tick, few enough to stay readable.
- **Fixed PRNG seed**, so a re-seed produces the same visits and a screenshot
  taken from it does not quietly stop matching.

It refuses to run against a database that already has records rather than
doubling them up, and there is a test for that.

The one invariant worth asserting is that every visit answers every field: the
compliance score is `verified / scoreable`, and a visit missing rows would be
scored against a different denominator than the row above it in the same table.

## The sticky bar ate a third of a phone screen

The inspection form pins a progress bar and two buttons to the bottom of the
viewport. At phone width the media query stacked the buttons on top of each
other, so the bar came to roughly 150px of an 844px screen - pinned, on the one
page you scroll the most, on the device the app is actually used on.

The two labels are "Back to home" and "Submit checklist". They fit side by side
at 390px with room to spare. Now they stay in a row with `flex: 1` each and the
progress line sits above them, which halves the bar.

Found by rendering at 390x844 and looking at it, which is the argument for
capturing the responsive screenshots rather than assuming a media query did what
it said.

## What was already right

Worth writing down, because most of this pass found nothing to fix:

- **No secrets, and the database is gitignored.** `checklist.db` is untracked and
  ignored, and there is nothing else to leak - the app has no accounts, no keys
  and no third-party calls.
- **`pip-audit` is clean.** Flask and pytest are the only dependencies.
- **The theming is a real toggle**, not a `prefers-color-scheme` block with a dead
  `[data-theme]` hook - which is what two other repos in this sweep turned out to
  have. It follows the system setting until someone picks, stores the choice, and
  the capture harness sets the same attribute the toggle does.
- **32 tests already existed**, several of them pinning specific bugs an earlier
  refactor fixed (unticking on edit, duplicate answer rows, the delete name
  check). They are recognisable as regression tests, which is the useful kind.

## Screenshots

18 images: six screens per theme plus three responsive per theme, real renders
against the demo data.

Two mechanical notes for the next Flask app:

- **Two zoom captures in one browser batch times the renderer out.** Every batch
  with a second capture in it failed with a CDP timeout, and the fix was a two
  second wait between the grab and the capture. Worth knowing before assuming the
  page is broken.
- **The theme is forced with `data-theme` on the root element**, which is exactly
  what the app's own toggle sets, so the images are the real thing rather than an
  approximation injected from outside.

## Added

CI, which did not exist: the suite on three Python versions, a smoke job that runs
`init-db` and `seed-demo` and then fetches the four pages that read the database,
and a dependency audit. An MIT `LICENSE`, which was missing while the README
implied one. `README-light.md`, generated.

## Left alone

- **No accounts, by design.** Anyone who can reach the site can edit or delete a
  record. The README and DEVDOC both say so plainly; adding auth is a product
  decision, not a documentation pass.
- **The delete confirmation is a typed name, not a password.** It guards against a
  misclick, which is what it is for, and the About page says exactly that.
