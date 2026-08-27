import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from messcheck import create_app  # noqa: E402


@pytest.fixture
def app():
    handle, path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    application = create_app({"TESTING": True, "DATABASE": path, "SECRET_KEY": "test"})
    yield application
    os.unlink(path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def fields(app):
    """The seeded fields, as plain dicts."""
    from messcheck import models

    with app.app_context():
        return [dict(row) for row in models.list_fields()]
