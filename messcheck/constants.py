"""Shared constants for the MessCheck app."""

APP_NAME = "MessCheck"
ORG_NAME = "IIITH Mess"

# Field types the checklist form knows how to render and store.
FIELD_TYPES = (
    ("checkbox", "Checkbox"),
    ("text", "Short text"),
    ("number", "Number"),
)
FIELD_TYPE_VALUES = tuple(value for value, _ in FIELD_TYPES)

# Suggested categories. Users may type a new one; these only seed the datalist
# and fix the display order of the known groups.
DEFAULT_CATEGORIES = (
    "Personal Hygiene",
    "Cleaning & Sanitization",
    "Food Storage",
    "Cooking & Serving",
    "Pest Control",
    "Equipment Maintenance",
    "Waste Management",
)

# Fields inserted the first time the database is created, so a fresh install
# has a usable checklist instead of an empty form.
SEED_FIELDS = (
    ("Staff wearing clean uniforms and hairnets", "checkbox", "Personal Hygiene"),
    ("Hands washed and gloves used while handling food", "checkbox", "Personal Hygiene"),
    ("No staff working while unwell", "checkbox", "Personal Hygiene"),
    ("Floors, walls and drains cleaned", "checkbox", "Cleaning & Sanitization"),
    ("Dining tables and chairs wiped between meals", "checkbox", "Cleaning & Sanitization"),
    ("Sanitiser available at wash points", "checkbox", "Cleaning & Sanitization"),
    ("Raw and cooked food stored separately", "checkbox", "Food Storage"),
    ("Cold storage temperature (deg C)", "number", "Food Storage"),
    ("Dry goods off the floor and sealed", "checkbox", "Food Storage"),
    ("Food cooked to safe temperature", "checkbox", "Cooking & Serving"),
    ("Serving counters covered and clean", "checkbox", "Cooking & Serving"),
    ("Leftovers labelled with date and time", "checkbox", "Cooking & Serving"),
    ("No signs of rodents or insects", "checkbox", "Pest Control"),
    ("Last pest control visit", "text", "Pest Control"),
    ("Refrigeration units working correctly", "checkbox", "Equipment Maintenance"),
    ("Exhaust and chimney filters cleaned", "checkbox", "Equipment Maintenance"),
    ("Wet and dry waste segregated", "checkbox", "Waste Management"),
    ("Bins covered and emptied daily", "checkbox", "Waste Management"),
)
