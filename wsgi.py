"""WSGI entry point for production hosts."""

from messcheck import create_app

application = create_app()
app = application
