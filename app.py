"""Entry point. `python app.py` runs the development server.

WSGI hosts (PythonAnywhere, gunicorn) should import `app` from this module.
"""

import os

from messcheck import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )
